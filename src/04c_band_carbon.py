"""Phase 4 수정(심사 대응): 시간대별 계수로 연관 추가 배출 재계산 + CNG 증회 결과의 승용차 계수 민감도

(1) β를 시간대(심야 22–05 / 새벽 05–07 / 주간 07–22)마다 그 시간대 안의 변동으로 따로 추정(03i)해 같은 시간대 행에만 적용.
    주 결과 = 심야·새벽(계수 유의) 합계. 주간은 추정값 그대로 따로 보고하되 합산하지 않는다(출발 계수 비유의·도착 계수 반대 부호).
    기존 시간대 공통 계수(M1) 결과(04_탄소.json headline1)는 '상한 시나리오'로 표기.
(2) 사각지대 셀 CNG 증회: 셀이 순감축으로 바뀌려면 승용차 g/km가 몇 배여야 하는지(손익분기 배수 = 버스 배출 ÷ 회피 배출)
    를 공통 계수·시간대별 계수 두 경우로 계산하고, 1.5·2·3배 × 재차인원 낙관(1.2)에서 순감축 셀 수를 센다.
출력: outputs/04c_시간대별_탄소.json, outputs/04c_구간별_배출.csv, outputs/04c_셀_보강.csv, outputs/04c_CNG_민감도.csv
"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).parent))
from common import *
import json, numpy as np, pandas as pd

PR = json.load(open(ROOT / "src" / "params.json", encoding="utf-8"))
G = PR["car_gco2_per_km"]["value"]
CF, CF_LO = PR["circuity"]["value"], PR["circuity"]["low"]
OCC, OCC_LO, OCC_HI = PR["occupancy"]["value"], PR["occupancy"]["low"], PR["occupancy"]["high"]
NWK, NWE = PR["annual_days"]["weekday"], PR["annual_days"]["weekend_holiday"]
GRID = PR["grid_tco2_per_mwh"]["value"]
SCEN = {"낙관": dict(occ=OCC_LO, cf=CF), "기본": dict(occ=OCC, cf=CF), "보수": dict(occ=OCC_HI, cf=CF_LO)}
BANDS = ["night", "dawn", "day"]
to_t = lambda pkm, occ, cf, g=G: pkm * cf / occ * g / 1e6

reg = pd.read_csv(OUT / "03_회귀표_시간대분리.csv")
b4 = reg[reg.model.str.startswith("B4")].set_index("var")
beta = {b: (b4.loc[f"So_{b}", "Estimate"], b4.loc[f"Sd_{b}", "Estimate"]) for b in BANDS}
boot = pd.read_csv(OUT / "03_부트스트랩_시간대.csv")

pan = pd.read_parquet(INTERIM / "02_패널.parquet", columns=["o", "d", "tbin", "daytype", "trips", "car", "S_o", "S_d", "car_dist_km", "dist_km"])
cell = pd.read_parquet(OUT / "03_셀.parquet")
pan = pan.merge(cell.groupby(["tbin", "daytype"]).p75.first().reset_index(), on=["tbin", "daytype"])
band = np.select([pan.tbin.isin(["22-24", "00-05"]), pan.tbin == "05-07"], ["night", "dawn"], "day")
go = (pan.p75 - pan.S_o).clip(lower=0).values; gd = (pan.p75 - pan.S_d).clip(lower=0).values
T = pan.trips.values; C = pan.car.values; Dk = pan.car_dist_km.fillna(pan.dist_km).values
annw = np.where(pan.daytype.values == "wk", NWK, NWE)
key = (pan.daytype + "|" + pan.tbin).values

def extra(bmap):
    """행별 (출발 성분, 도착 성분) 일평균 추가 차량 '인' 통행. bmap: band → (β_o, β_d)"""
    bo = np.select([band == b for b in BANDS], [bmap[b][0] for b in BANDS])
    bd = np.select([band == b for b in BANDS], [bmap[b][1] for b in BANDS])
    eo, ed = T * (-bo) * go, T * (-bd) * gd
    tot = eo + ed
    s = np.where(tot > C, C / np.where(tot > 0, tot, 1), 1.0)
    return eo * s, ed * s

def pkm_by_band(bmap):
    eo, ed = extra(bmap); pk = (eo + ed) * Dk * annw
    return pd.Series(pk).groupby(band).sum()

res = {"beta_band": {b: {"beta_o": beta[b][0], "beta_d": beta[b][1],
                         "p_o": float(b4.loc[f"So_{b}", "Pr(>|t|)"]), "p_d": float(b4.loc[f"Sd_{b}", "Pr(>|t|)"])} for b in BANDS},
       "n_boot": int(len(boot))}
pb0 = pkm_by_band(beta)
bt = pd.DataFrame([pkm_by_band({b: (r[f"So_{b}"], r[f"Sd_{b}"]) for b in BANDS}) for _, r in boot.iterrows()])
bt["nd"] = bt.night + bt.dawn
pb0["nd"] = pb0.night + pb0.dawn
for k in ["nd", "night", "dawn", "day"]:
    lo, hi = np.percentile(bt[k], [2.5, 97.5])
    res[f"band_{k}"] = {s: {"t": to_t(pb0[k], **p), "ci_lo": to_t(lo, **p), "ci_hi": to_t(hi, **p)} for s, p in SCEN.items()}
res["band_nd_range"] = [res["band_nd"]["보수"]["ci_lo"], res["band_nd"]["낙관"]["ci_hi"]]
c4 = json.load(open(OUT / "04_탄소.json", encoding="utf-8"))
res["common_beta_upper_t"] = c4["headline1"]["기본"]["t"]
res["common_beta_night_t"] = c4["headline1"]["기본"]["t"] * c4["share_night"]  # 공통 계수의 심야(22–05) 몫
res["nd_vs_common"] = res["band_nd"]["기본"]["t"] / res["common_beta_upper_t"]
print("시간대별 β:", {b: tuple(round(x, 4) for x in beta[b]) for b in BANDS})
print("심야·새벽 tCO2/년:", {s: {k: round(v) for k, v in d.items()} for s, d in res["band_nd"].items()})
print("주간(합산 안 함) tCO2/년:", {s: {k: round(v) for k, v in d.items()} for s, d in res["band_day"].items()})

# 구간별(기본 시나리오)
eo, ed = extra(beta)
pk = (eo + ed) * Dk * annw
by = pd.DataFrame({"key": key, "pk": pk}).groupby("key").pk.sum().reset_index()
by[["daytype", "tbin"]] = by.key.str.split("|", expand=True)
by["tco2_ann"] = to_t(by.pk, **SCEN["기본"])
bk = pd.concat([pd.Series(sum(extra({b: (r[f"So_{b}"], r[f"Sd_{b}"]) for b in BANDS})) * Dk * annw).groupby(key).sum()
                for _, r in boot.iterrows()], axis=1)
by["tco2_lo"] = to_t(bk.loc[by.key].quantile(0.025, axis=1).values, **SCEN["기본"])
by["tco2_hi"] = to_t(bk.loc[by.key].quantile(0.975, axis=1).values, **SCEN["기본"])
by["band"] = np.select([by.tbin.isin(["22-24", "00-05"]), by.tbin == "05-07"], ["night", "dawn"], "day")
by.drop(columns="key").to_csv(OUT / "04c_구간별_배출.csv", index=False, encoding="utf-8-sig")

# ---- (2) 셀 단위 회피 배출: 주 결과(주간 계수 0) ----
bmain = {"night": beta["night"], "dawn": beta["dawn"], "day": (0.0, 0.0)}
eo, ed = extra(bmain)
pan["exkm_o"], pan["exkm_d"] = eo * Dk, ed * Dk
co = pan.groupby(["o", "tbin", "daytype"]).exkm_o.sum().rename_axis(["dong", "tbin", "daytype"])
cd = pan.groupby(["d", "tbin", "daytype"]).exkm_d.sum().rename_axis(["dong", "tbin", "daytype"])
cb = pd.concat([co, cd], axis=1).fillna(0).sum(axis=1).rename("extra_vkm_band").reset_index()
# 전체 셀의 일평균 추가 차량 인통행(주 결과 규칙) — 프로토타입 동 카드용
pan["ex_o"], pan["ex_d"] = eo, ed
et = pd.concat([pan.groupby(["o", "tbin", "daytype"]).ex_o.sum().rename_axis(["dong", "tbin", "daytype"]),
                pan.groupby(["d", "tbin", "daytype"]).ex_d.sum().rename_axis(["dong", "tbin", "daytype"])], axis=1).fillna(0).sum(axis=1)
et.rename("extra_trips_band").reset_index().to_csv(OUT / "04c_셀_추가통행.csv", index=False, encoding="utf-8-sig")
c = pd.read_csv(OUT / "04_셀_보강.csv", dtype={"dong": str})
c = c.merge(cb, on=["dong", "tbin", "daytype"], how="left").fillna({"extra_vkm_band": 0})
c["avoided_t_band"] = to_t(c.extra_vkm_band * c.ann_days, **SCEN["기본"])
c["net_cng_t_band"] = c.avoided_t_band - c.bus_t_cng
# 손익분기 승용차 계수 배수(회피 배출이 양수인 셀만 정의, 0 이하면 무한대)
for tag, col in (("common", "avoided_t"), ("band", "avoided_t_band")):
    c[f"be_mult_{tag}"] = np.where(c[col] > 0, c.bus_t_cng / c[col].where(c[col] > 0), np.inf)
c["drt_net_band"] = c.avoided_t_band - c.bus_km_yr * PR["drt_gco2_per_km"]["value"] / 1e6
c["ebus_be_band"] = c.avoided_t_band * 1000 / (c.bus_km_yr * GRID)
c.to_csv(OUT / "04c_셀_보강.csv", index=False, encoding="utf-8-sig")
occ_adj = OCC / OCC_LO  # 재차인원 1.4 → 1.2 (낙관)
rows = []
for tag in ("common", "band"):
    for m in (1.0, 1.5, 2.0, 3.0):
        for occ_name, k in (("기본 1.4", 1.0), ("낙관 1.2", occ_adj)):
            rows.append(dict(beta=tag, car_mult=m, car_g_km=G * m, occupancy=occ_name,
                             pos_cells=int((c[f"be_mult_{tag}"] < m * k).sum()), cells=int(len(c)),
                             net_t_all=float((c["avoided_t" if tag == "common" else "avoided_t_band"] * m * k - c.bus_t_cng).sum())))
sens = pd.DataFrame(rows); sens.to_csv(OUT / "04c_CNG_민감도.csv", index=False, encoding="utf-8-sig")
print(sens.to_string())
fin = lambda s: s[np.isfinite(s)]
for tag in ("common", "band"):
    s = c[f"be_mult_{tag}"]
    res[f"cng_be_mult_{tag}"] = {"min": float(fin(s).min()) if len(fin(s)) else None, "median_finite": float(fin(s).median()) if len(fin(s)) else None,
                                 "p10": float(s.quantile(.1)), "n_inf": int((~np.isfinite(s)).sum())}
res["cng_be_gkm_common_min"] = G * res["cng_be_mult_common"]["min"]
res["cng_be_gkm_common_min_occ12"] = G * res["cng_be_mult_common"]["min"] / occ_adj
res["cng_pos_cells_3x_occ12_common"] = int(sens.query("beta=='common' and car_mult==3 and occupancy=='낙관 1.2'").pos_cells.iloc[0])
res["cng_pos_cells_3x_occ12_band"] = int(sens.query("beta=='band' and car_mult==3 and occupancy=='낙관 1.2'").pos_cells.iloc[0])
res["gasoline_kgco2_per_l"] = PR["ipcc_gasoline_kgCO2_per_TJ"]["value"] * PR["ncv_gasoline_MJ_per_L"]["value"] / 1e6
res["kmpl_at_3x"] = res["gasoline_kgco2_per_l"] * 1000 / (G * 3)
res["band_avoided_t_blind"] = float(c.avoided_t_band.sum()); res["band_cng_neg"] = int((c.net_cng_t_band < 0).sum())
res["band_drt_pos"] = int((c.drt_net_band > 0).sum())
res["band_drt_pos_night"] = int(((c.drt_net_band > 0) & c.tbin.isin(["22-24", "00-05", "05-07"])).sum())
res["band_ebus_be_med_nd"] = float(c[c.tbin.isin(["22-24", "00-05", "05-07"])].ebus_be_band.median())
json.dump(res, open(OUT / "04c_시간대별_탄소.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
print(json.dumps({k: v for k, v in res.items() if not k.startswith("band_") or k in ("band_nd",)}, ensure_ascii=False, indent=1, default=float))
