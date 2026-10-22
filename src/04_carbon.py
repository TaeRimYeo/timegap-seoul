"""Phase 4: 탄소 계산 (연관 기반 추정) + RQ4 보강 순감축

배출(tCO2) = 추가 차량 '인' 통행 × 직선거리 × 우회계수 ÷ 재차인원 × 승용차 g/km
불확실성: 출발 동 블록 부트스트랩 β(200회)로 셀 추가통행 재계산 → 95% 구간, × 낙관/기본/보수 계수 시나리오
보강: 시간 사각지대 셀의 공급을 p75로 → 추가 버스 운행 = (e^p75 − e^S)회/시 × 구간 시간 × 연간 일수
     운행 1회당 버스km = 노선 길이 ÷ 노선이 지나는 동 수 (정류소 좌표 직선합 × 우회계수, 데이터 산출)
     CNG 버스 kgCO2/km = 순발열량(도시가스 38.5 MJ/Nm3) × IPCC 56,100 kg/TJ ÷ 1.8 km/m3
     전기버스: 국내 전비 원문 미확보 → 셀 순감축이 0이 되는 손익분기 전비(kWh/km) = 회피 배출 ÷ (버스km × 전력계수)
출력: outputs/04_탄소.json, outputs/04_구간별_배출.csv, outputs/04_셀_보강.csv, outputs/04_우선순위_상위10.csv
"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).parent))
from common import *
import json, duckdb, numpy as np, pandas as pd, geopandas as gpd

PR = json.load(open(ROOT / "src" / "params.json", encoding="utf-8"))
G = PR["car_gco2_per_km"]["value"]
CF, CF_LO = PR["circuity"]["value"], PR["circuity"]["low"]
OCC, OCC_LO, OCC_HI = PR["occupancy"]["value"], PR["occupancy"]["low"], PR["occupancy"]["high"]
BUS_KG_KM = PR["ncv_lng_city_gas_MJ_per_Nm3"]["value"] * PR["ipcc_cng_kgCO2_per_TJ"]["value"] / 1e6 / PR["cng_bus_km_per_m3"]["value"]
GRID = PR["grid_tco2_per_mwh"]["value"]  # t/MWh = kg/kWh
NWK, NWE = PR["annual_days"]["weekday"], PR["annual_days"]["weekend_holiday"]
SCEN = {"낙관": dict(occ=OCC_LO, cf=CF), "기본": dict(occ=OCC, cf=CF), "보수": dict(occ=OCC_HI, cf=CF_LO)}
HOURS = {b: len(TBIN_HOURS[b]) for b in TBINS}
print(f"CNG 버스 {BUS_KG_KM:.3f} kgCO2/km, 승용차 {G} g/km")

# ---- 부트스트랩 β로 셀 추가 통행 재계산 ----
pan = pd.read_parquet(INTERIM / "02_패널.parquet", columns=["o", "d", "tbin", "daytype", "trips", "car", "S_o", "S_d", "car_dist_km", "dist_km"])
cell = pd.read_parquet(OUT / "03_셀.parquet")
q = cell.groupby(["tbin", "daytype"]).p75.first().reset_index()
pan = pan.merge(q, on=["tbin", "daytype"])
go = (pan.p75 - pan.S_o).clip(lower=0).values; gd = (pan.p75 - pan.S_d).clip(lower=0).values
T = pan.trips.values; C = pan.car.values; Dk = pan.car_dist_km.fillna(pan.dist_km).values
annw = np.where(pan.daytype.values == "wk", NWK, NWE)
key = (pan.daytype + "|" + pan.tbin).values
def person_km(bo, bd):
    eo, ed = T * (-bo) * go, T * (-bd) * gd
    tot = eo + ed
    s = np.where(tot > C, C / np.where(tot > 0, tot, 1), 1.0)
    return (eo + ed) * s * Dk  # 일평균 인·km(직선)
reg = pd.read_csv(OUT / "03_회귀표.csv"); m1 = reg[reg.model.str.startswith("M1")].set_index("var")
b0 = (m1.loc["S_o", "coef"], m1.loc["S_d", "coef"])
pk0 = person_km(*b0)
boot = pd.read_csv(OUT / "03_부트스트랩.csv")
bt_tot, bt_bin = [], []
for bo, bd in zip(boot.beta_o, boot.beta_d):
    pk = person_km(bo, bd)
    bt_tot.append((pk * annw).sum())
    bt_bin.append(pd.Series(pk * annw).groupby(key).sum())
bt_bin = pd.concat(bt_bin, axis=1)
def to_t(pkm, occ, cf): return pkm * cf / occ * G / 1e6
res = {"bus_kgco2_per_km_cng": BUS_KG_KM, "params": {k: v.get("value") if isinstance(v, dict) else v for k, v in PR.items() if not k.startswith("_")}}
ann_pk0 = (pk0 * annw).sum()
lo, hi = np.percentile(bt_tot, [2.5, 97.5])
res["headline1"] = {s: {"t": to_t(ann_pk0, **p), "ci_lo": to_t(lo, **p), "ci_hi": to_t(hi, **p)} for s, p in SCEN.items()}
res["headline1_range"] = [to_t(lo, **SCEN["낙관"]) if False else to_t(lo, **SCEN["보수"]), to_t(hi, **SCEN["낙관"])]
res["extra_vehicle_km_base"] = ann_pk0 * CF / OCC
print("① 연관 추가 배출 tCO2/년:", {s: {k: round(v) for k, v in d.items()} for s, d in res["headline1"].items()})
# 구간별
bb = pd.DataFrame({"key": key, "pk": pk0 * annw}).groupby("key").pk.sum()
by = pd.DataFrame({"key": bb.index, "pk": bb.values})
by[["daytype", "tbin"]] = by.key.str.split("|", expand=True)
p = SCEN["기본"]
by["tco2_ann"] = to_t(by.pk, **p)
by["tco2_lo"] = to_t(bt_bin.loc[by.key].quantile(0.025, axis=1).values, **p)
by["tco2_hi"] = to_t(bt_bin.loc[by.key].quantile(0.975, axis=1).values, **p)
by["share"] = by.tco2_ann / by.tco2_ann.sum()
by.drop(columns="key").to_csv(OUT / "04_구간별_배출.csv", index=False, encoding="utf-8-sig")
night = by.tbin.isin(["22-24", "00-05"])
res["share_nonnight"] = float(by.loc[~night, "share"].sum())
res["share_wk_0916"] = float(by.loc[(by.daytype == "wk") & by.tbin.isin(["09-12", "12-16"]), "share"].sum())
res["share_weekend"] = float(by.loc[by.daytype == "we", "share"].sum())
res["share_night"] = float(by.loc[night, "share"].sum())

# ---- 노선 1회 통과당 버스km (데이터 산출) ----
st = pd.read_excel(RAW / "버스정류소" / "서울시버스정류소위치정보(20260902).xlsx", dtype={"NODE_ID": str})
st.columns = ["stop_id", "ars", "name", "x", "y", "stype"]
gst = gpd.GeoDataFrame(st, geometry=gpd.points_from_xy(st.x, st.y), crs=4326).to_crs(5179)
g = gpd.read_file(EXT / "HangJeongDong_ver20260701.geojson"); g = g[g.sido == "11"].to_crs(5179); g["dong"] = g.adm_cd2.str[:8]
gst = gpd.sjoin(gst, g[["dong", "geometry"]], predicate="within")
gst["X"], gst["Y"] = gst.geometry.x, gst.geometry.y
u = to_utf8_tmp(RAW / "버스운행" / "tpss_sta_route_hturn_2026.09.07-09.13.csv")
con = duckdb.connect()
rs = con.execute(f"SELECT DISTINCT route_id, stop_id, try_cast(seq AS INT) seq FROM {bus_csv_sql(u)} WHERE date='20260908'").fetchdf(); u.unlink()
rs = rs.merge(gst[["stop_id", "X", "Y", "dong"]], on="stop_id").sort_values(["route_id", "seq"])
rs["dx"] = np.hypot(rs.groupby("route_id").X.diff(), rs.groupby("route_id").Y.diff())
rs = rs[rs.dx.isna() | (rs.dx < 3000)]  # 서울 밖 구간·좌표 누락으로 생긴 점프 제외
rt = rs.groupby("route_id").agg(km=("dx", lambda s: s.sum() / 1000 * CF), n_dong=("dong", "nunique"), n_stop=("stop_id", "count"))
rt = rt[(rt.n_stop >= 5) & (rt.km > 0)]
rt["km_per_dong"] = rt.km / rt.n_dong
KM_PASS = float(rt.km_per_dong.median())
res["bus_km_per_dong_pass"] = KM_PASS; res["n_routes_for_km"] = int(len(rt))
print(f"노선 {len(rt)}개, 동 1개 통과당 버스km 중앙값 {KM_PASS:.2f} km (IQR {rt.km_per_dong.quantile(.25):.2f}~{rt.km_per_dong.quantile(.75):.2f})")

# ---- RQ4: 시간 사각지대 셀 보강 ----
c = cell[cell.blind].copy()
c["add_runs_h"] = (np.exp(c.p75) - np.exp(c.S)).clip(lower=0)
c["ann_days"] = np.where(c.daytype == "wk", NWK, NWE)
c["add_runs_yr"] = c.add_runs_h * c.tbin.map(HOURS) * c.ann_days
c["bus_km_yr"] = c.add_runs_yr * KM_PASS
c["avoided_t"] = to_t(c.extra_vkm * c.ann_days, **SCEN["기본"])
c["avoided_t_lo"] = to_t(c.extra_vkm * c.ann_days, **SCEN["보수"])
c["avoided_t_hi"] = to_t(c.extra_vkm * c.ann_days, **SCEN["낙관"])
c["bus_t_cng"] = c.bus_km_yr * BUS_KG_KM / 1000
c["net_cng_t"] = c.avoided_t - c.bus_t_cng
c["net_cng_t_lo"] = c.avoided_t_lo - c.bus_t_cng
c["net_cng_t_hi"] = c.avoided_t_hi - c.bus_t_cng
c["net_kg_per_run"] = c.net_cng_t * 1000 / c.add_runs_yr
c["ebus_breakeven_kwh_km"] = c.avoided_t * 1000 / (c.bus_km_yr * GRID)  # 이 전비 이하면 전기버스 순감축 > 0
c["beneficiary_trips_yr"] = (c.trips_out + c.trips_in) * c.ann_days
c.to_csv(OUT / "04_셀_보강.csv", index=False, encoding="utf-8-sig")
res["blind_cells"] = int(len(c))
res["neg_cells_cng"] = int((c.net_cng_t < 0).sum())
res["neg_cells_cng_lo"] = int((c.net_cng_t_lo < 0).sum())
res["neg_cells_by_tbin"] = {f"{k[0]}|{k[1]}": int(v) for k, v in c[c.net_cng_t < 0].groupby(["daytype", "tbin"]).size().items()}
res["neg_cells_night_share"] = float(c[c.net_cng_t < 0].tbin.isin(["22-24", "00-05", "05-07"]).mean()) if (c.net_cng_t < 0).any() else 0.0
pos = c[c.net_cng_t > 0].sort_values("net_cng_t", ascending=False)
N = 20
top = pos.head(N)
res["topN"] = N
res["headline2_topN_net_t"] = {"보수": float(top.net_cng_t_lo.sum()), "기본": float(top.net_cng_t.sum()), "낙관": float(top.net_cng_t_hi.sum())}
res["headline2_all_pos_net_t"] = float(pos.net_cng_t.sum()); res["n_pos_cells"] = int(len(pos))
res["headline3_kg_per_run_topN"] = float(top.net_cng_t.sum() * 1000 / top.add_runs_yr.sum())
res["headline3_kg_per_run_topN_range"] = [float(top.net_cng_t_lo.sum() * 1000 / top.add_runs_yr.sum()), float(top.net_cng_t_hi.sum() * 1000 / top.add_runs_yr.sum())]
res["topN_add_runs_yr"] = float(top.add_runs_yr.sum()); res["topN_bus_km_yr"] = float(top.bus_km_yr.sum())
res["topN_beneficiary_trips_yr"] = float(top.beneficiary_trips_yr.sum())
res["topN_share_nonnight"] = float((~top.tbin.isin(["22-24", "00-05"])).mean())
neg = c[c.net_cng_t < 0]
res["neg_cells_median_breakeven_kwh_km"] = float(neg.ebus_breakeven_kwh_km.median()) if len(neg) else None
res["neg_cells_trips_out_median"] = float(neg.trips_out.median()) if len(neg) else None
res["pos_cells_trips_out_median"] = float(pos.trips_out.median())
t10 = pos.head(10)[["dong", "adm_nm", "daytype", "tbin", "space_good", "old_share", "S", "p75", "add_runs_h", "trips_out", "extra_trips", "avoided_t", "bus_t_cng", "net_cng_t", "net_kg_per_run", "ebus_breakeven_kwh_km", "expo"]]
t10.to_csv(OUT / "04_우선순위_상위10.csv", index=False, encoding="utf-8-sig")
json.dump(res, open(OUT / "04_탄소.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
print(json.dumps({k: v for k, v in res.items() if k != "params"}, ensure_ascii=False, indent=1, default=float))
print(t10.round(3).to_string())
