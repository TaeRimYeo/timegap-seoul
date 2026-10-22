"""3-3 파업 자연실험 (외생 충격 하의 반응; 인과 해석은 동시 조치 등 한계 명시)
- 1단계(b): 생활이동 '버스' 수단 통행의 파업일 급감(대조일 대비)
- 2단계 이중차분: 출발 동 d × 일자 t (× 시간 구간). 처치 강도 = 파업 전(01-06·07) 동별 버스(일반+광역) 수단 비중.
    car_share_{i,t,b} ~ BusShare_i × Strike_t | dong^tbin + date^tbin   (weights=trips, CRV1 dong)
    total trips(log)도 같은 식.
- 공급 기반 비교: car_share ~ S_{i,t,b} | dong^tbin + date^tbin  (파업일 동별 버스 공급 하락으로 식별) → 3-2 β와 비교
대조일: 01-06(화)·07(수)·20(화)·21(수), 파업일: 01-13(화)·14(수)
출력: outputs/03_파업.json, outputs/03_파업_일별수단.csv
"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).parent))
from common import *
import duckdb, zipfile, shutil, json, numpy as np, pandas as pd, geopandas as gpd, pyfixest as pf

DAYS = ["20260106", "20260107", "20260113", "20260114", "20260120", "20260121"]
STRIKE = {"20260113", "20260114"}
con = duckdb.connect()
files = ", ".join(f"'{(INTERIM / f'od_{d}.parquet').as_posix()}'" for d in DAYS)
od = con.execute(f"""SELECT o, d, hour, mode, trips, regexp_extract(filename, 'od_(\\d{{8}})', 1) AS date FROM read_parquet([{files}], filename=true)""").fetchdf()
# 1단계(b)
m = od.groupby(["date", "mode"]).trips.sum().unstack()
m.columns = [MODES.get(c, "차량<500m") for c in m.columns]
m.to_csv(OUT / "03_파업_일별수단.csv", encoding="utf-8-sig")
ctrl = m.loc[[d for d in DAYS if d not in STRIKE]].mean(); stk = m.loc[sorted(STRIKE)].mean()
stage1 = {k: float(stk[k] / ctrl[k] - 1) for k in ["일반버스", "광역버스", "지하철", "차량", "도보", "기타"]}
print("파업일/대조일 - 1:", {k: round(v, 3) for k, v in stage1.items()})

# 동별 일별 버스 공급 (Phase 1과 같은 노선 중복 제거)
st = pd.read_excel(RAW / "버스정류소" / "서울시버스정류소위치정보(20260902).xlsx", dtype={"NODE_ID": str})
st.columns = ["stop_id", "ars", "name", "x", "y", "stype"]
g = gpd.read_file(EXT / "HangJeongDong_ver20260701.geojson"); g = g[g.sido == "11"].to_crs(5179); g["dong"] = g.adm_cd2.str[:8]
st = gpd.sjoin(gpd.GeoDataFrame(st, geometry=gpd.points_from_xy(st.x, st.y), crs=4326).to_crs(5179), g[["dong", "geometry"]], predicate="within")
con.register("stop_dong", st[["stop_id", "dong"]].drop_duplicates())
tmpd = TMP / "bus202601s"; tmpd.mkdir(parents=True, exist_ok=True)
frames = []
with zipfile.ZipFile(EXT / "tpss_sta_route_hturn_202601.zip") as z:
    for n in z.namelist():
        if not any(k in n for k in ["01.05-01.11", "01.12-01.18", "01.19-01.25"]): continue
        z.extract(n, tmpd); u = to_utf8_tmp(tmpd / n); (tmpd / n).unlink()
        dl = ",".join(f"'{d}'" for d in DAYS)
        con.execute(f"CREATE OR REPLACE TABLE b AS SELECT * FROM {bus_csv_sql(u)} WHERE date IN ({dl})"); u.unlink()
        unp = " UNION ALL ".join(f"SELECT date, route_id, stop_id, {h} AS hour, coalesce(try_cast(h{h:02d} AS INT),0) runs FROM b" for h in range(24))
        frames.append(con.execute(f"""WITH u AS ({unp}) SELECT date, dong, hour, sum(mx) runs FROM (
            SELECT u.date, s.dong, u.hour, u.route_id, max(u.runs) mx FROM u JOIN stop_dong s USING(stop_id) GROUP BY ALL) GROUP BY ALL""").fetchdf())
shutil.rmtree(tmpd, ignore_errors=True)
bus = pd.concat(frames)
grid = pd.MultiIndex.from_product([g.dong, DAYS, range(24)], names=["dong", "date", "hour"]).to_frame(index=False)
bus = grid.merge(bus, how="left").fillna({"runs": 0})
sub = pd.read_parquet(OUT / "01_공급지표_시간.parquet")
sub = sub[sub.daytype == "wk"][["dong", "hour", "sub_trains_h"]]
bus = bus.merge(sub, on=["dong", "hour"])
bus["tbin"] = bus.hour.map(hour_to_tbin)
sb = bus.groupby(["dong", "date", "tbin"], as_index=False).agg(bus_runs_h=("runs", "mean"), sub_trains_h=("sub_trains_h", "mean"))
sb["S"] = np.log1p(sb.bus_runs_h + 3 * sb.sub_trains_h)

# 출발 동 × 일 × 구간 패널 (o≠d, 4수단)
od = od[(od.o != od.d) & od["mode"].isin([4, 5, 6, 8])]
od["tbin"] = od.hour.map(hour_to_tbin)
pp = od.pivot_table(index=["o", "date", "tbin"], columns="mode", values="trips", aggfunc="sum", fill_value=0).reset_index()
pp.columns = ["dong", "date", "tbin", "gbus", "bus", "subway", "car"]
pp["trips"] = pp[["gbus", "bus", "subway", "car"]].sum(axis=1)
pp = pp[pp.trips >= 20]
pp["car_share"] = pp.car / pp.trips
pre = pp[pp.date.isin(["20260106", "20260107"])].groupby("dong")[["bus", "gbus", "trips"]].sum()
pp["bus_share_pre"] = pp.dong.map((pre.bus + pre.gbus) / pre.trips)
pp["strike"] = pp.date.isin(STRIKE).astype(int)
pp["treat"] = pp.bus_share_pre * pp.strike
pp["log_trips"] = np.log(pp.trips)
pp = pp.merge(sb, on=["dong", "date", "tbin"], how="left")
res = {"stage1_change": stage1}
for name, f in {"did_car_share": "car_share ~ treat | dong^tbin + date^tbin",
                "did_log_trips": "log_trips ~ treat | dong^tbin + date^tbin",
                "supply_car_share": "car_share ~ S | dong^tbin + date^tbin"}.items():
    mm = pf.feols(f, data=pp, weights="trips", vcov={"CRV1": "dong"})
    t = mm.tidy().iloc[0]
    res[name] = dict(coef=float(t["Estimate"]), se=float(t["Std. Error"]), p=float(t["Pr(>|t|)"]), lo=float(t["2.5%"]), hi=float(t["97.5%"]), n=int(mm._N))
    print(name, res[name])
dS = sb.assign(strike=sb.date.isin(STRIKE)).groupby(["dong", "strike"]).S.mean().unstack()
res["mean_dS_strike"] = float((dS[True] - dS[False]).mean())
res["bus_share_pre_mean"] = float(pre.eval("(bus+gbus)/trips").mean())
bd = pd.read_csv(OUT / "03_파업_버스운행_일별.csv", dtype={"date": str}).set_index("date")  # 03d 산출
ctrl_runs = bd.loc[[d for d in DAYS if d not in STRIKE], "runs_seoul_stops"].mean()
res["bus_runs_seoul_stops_change"] = float(bd.loc[sorted(STRIKE), "runs_seoul_stops"].mean() / ctrl_runs - 1)
res["bus_runs_0115_vs_ctrl"] = float(bd.loc["20260115", "runs_seoul_stops"] / ctrl_runs - 1)
# 차량 비중 원시 변화(서울 전체)
agg = pp.groupby("strike")[["car", "trips"]].sum(); res["car_share_ctrl"] = float(agg.loc[0, "car"] / agg.loc[0, "trips"]); res["car_share_strike"] = float(agg.loc[1, "car"] / agg.loc[1, "trips"])
json.dump(res, open(OUT / "03_파업.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
pp.to_parquet(INTERIM / "03_파업패널.parquet", index=False)
