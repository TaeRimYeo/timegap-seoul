"""Phase 3-2b · 3-5 · 3-5b · 3-6(a): 추가 차량 통행, 시간 사각지대 셀, 공간-시간 불일치, 공백 노출 집중도

- β: outputs/03_회귀표.csv 의 M1 (S_o, S_d)
- 반사실: S < p75(같은 구간·요일구분의 427개 동 분포)인 셀만 p75로 올림(관측 범위 안).
- OD 행별 추가 차량 통행 = trips × [−β_o·max(0, p75−S_o) − β_d·max(0, p75−S_d)], 차량 통행 수를 넘지 않게 상한.
    출발 성분은 출발 셀(o, tbin, daytype)에, 도착 성분은 도착 셀(d, …)에 귀속 → 셀 합 = 전체 합(1회 계산).
- 시간 사각지대 셀: S 하위 x%(같은 구간·요일구분) AND Δ = −β_o(p75−S) 상위 y%(전체 셀 풀) AND 셀 출발 통행 ≥ 50/일.
- 차량km = 추가 차량 통행 × 차량 통행가중 평균 이동거리(km, 직선) — 우회계수는 Phase 4에서 적용.
출력: outputs/03_셀.parquet, outputs/03_동.csv, outputs/03_요약.json, outputs/logs/03_analysis.txt
"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).parent))
from common import *
import pandas as pd, numpy as np, json, io
log = io.StringIO()
def P(*a):
    print(*a, flush=True); print(*a, file=log)

X = int(sys.argv[1]) if len(sys.argv) > 1 else 20
Y = int(sys.argv[2]) if len(sys.argv) > 2 else 20
SPACE_T = int(sys.argv[3]) if len(sys.argv) > 3 else 50
QUIET = len(sys.argv) > 4

reg = pd.read_csv(OUT / "03_회귀표.csv")
m1 = reg[reg.model.str.startswith("M1")].set_index("var")
b_o, b_d = m1.loc["S_o", "coef"], m1.loc["S_d", "coef"]

sup = pd.read_parquet(OUT / "01_공급지표.parquet")
q = sup.groupby(["tbin", "daytype"]).S.agg(p75=lambda s: s.quantile(.75), px=lambda s: s.quantile(X / 100)).reset_index()
sup = sup.merge(q, on=["tbin", "daytype"])
sup["gap"] = (sup.p75 - sup.S).clip(lower=0)

pan = pd.read_parquet(INTERIM / "02_패널.parquet")
pan = pan.merge(q[["tbin", "daytype", "p75"]], on=["tbin", "daytype"])
pan["gap_o"] = (pan.p75 - pan.S_o).clip(lower=0)
pan["gap_d"] = (pan.p75 - pan.S_d).clip(lower=0)
pan["ex_o"] = pan.trips * (-b_o) * pan.gap_o
pan["ex_d"] = pan.trips * (-b_d) * pan.gap_d
tot = pan.ex_o + pan.ex_d
scale = np.where(tot > pan.car, pan.car / tot.replace(0, np.nan), 1.0)
P("상한(차량 통행 수) 적용 행 비율", round(float((tot > pan.car).mean()), 5))
pan["ex_o"] *= np.nan_to_num(scale, nan=1.0); pan["ex_d"] *= np.nan_to_num(scale, nan=1.0)
pan["cdist"] = pan.car_dist_km.fillna(pan.dist_km)
pan["exkm_o"] = pan.ex_o * pan.cdist; pan["exkm_d"] = pan.ex_d * pan.cdist

# 셀 단위 집계
co = pan.groupby(["o", "tbin", "daytype"]).agg(trips_out=("trips", "sum"), car_out=("car", "sum"), ex_o=("ex_o", "sum"), exkm_o=("exkm_o", "sum")).reset_index().rename(columns={"o": "dong"})
cd = pan.groupby(["d", "tbin", "daytype"]).agg(trips_in=("trips", "sum"), ex_d=("ex_d", "sum"), exkm_d=("exkm_d", "sum")).reset_index().rename(columns={"d": "dong"})
cell = sup.merge(co, on=["dong", "tbin", "daytype"], how="left").merge(cd, on=["dong", "tbin", "daytype"], how="left").fillna(0)
cell["extra_trips"] = cell.ex_o + cell.ex_d
cell["extra_vkm"] = cell.exkm_o + cell.exkm_d
cell["delta"] = -b_o * cell.gap
cell["low_S"] = cell.S <= cell.px
dthr = cell.delta.quantile(1 - Y / 100)
cell["high_delta"] = cell.delta >= dthr
cell["blind"] = cell.low_S & cell.high_delta & (cell.trips_out >= 50)
acc = pd.read_csv(OUT / "02_동지표.csv", dtype={"dong": str})
cell = cell.merge(acc[["dong", "adm_nm", "sggnm", "cov_art", f"good{SPACE_T}", "old_share", "pop", "pop65"]].rename(columns={f"good{SPACE_T}": "space_good"}), on="dong", how="left")

# 공백 노출 인구(인원×시간): 생활인구 2025-09 (동, 시, 요일구분) 평균 → 구간 합
lp = pd.read_parquet(INTERIM / "02_생활인구.parquet")
for ym, col in (("202509", "expo"), ("202607", "expo_2607")):
    e = lp[lp.ym == ym].groupby(["dong", "daytype", "tbin"], as_index=False)["pop"].sum().rename(columns={"pop": col})
    cell = cell.merge(e, on=["dong", "daytype", "tbin"], how="left")

# 연간 환산: 2026년 달력(python holidays KR) 평일 245일, 주말·공휴일 120일
NWK, NWE = 245, 120
cell["ann_w"] = np.where(cell.daytype == "wk", NWK, NWE)
if not QUIET: cell.to_parquet(OUT / "03_셀.parquet", index=False)

res = {"beta_o": b_o, "beta_d": b_d, "x": X, "y": Y, "space_t": SPACE_T, "delta_thr": dthr}
ann = lambda s: float((s * cell.ann_w).sum())
res["extra_trips_ann"] = ann(cell.extra_trips)
res["extra_vkm_ann_crow"] = ann(cell.extra_vkm)
res["car_trips_ann_panel"] = ann(cell.car_out)
res["extra_share_of_car"] = res["extra_trips_ann"] / res["car_trips_ann_panel"]
# 3-2b 시간 구간별 분해
by = cell.groupby(["daytype", "tbin"]).apply(lambda x: pd.Series({"extra_trips_day": x.extra_trips.sum(), "extra_vkm_day": x.extra_vkm.sum(),
                                                                     "extra_vkm_ann": (x.extra_vkm * x.ann_w).sum()})).reset_index()
by["share_vkm_ann"] = by.extra_vkm_ann / by.extra_vkm_ann.sum()
if not QUIET: by.to_csv(OUT / "03_구간별_추가차량.csv", index=False, encoding="utf-8-sig")
night = by.tbin.isin(["22-24", "00-05"])
res["share_nonnight"] = float(by.loc[~night, "share_vkm_ann"].sum())
res["share_daytime_offpeak_wk_0916"] = float(by.loc[(by.daytype == "wk") & by.tbin.isin(["09-12", "12-16"]), "share_vkm_ann"].sum())
res["share_weekend_all"] = float(by.loc[by.daytype == "we", "share_vkm_ann"].sum())
res["share_weekend_day_0922"] = float(by.loc[(by.daytype == "we") & ~night & (by.tbin != "05-07"), "share_vkm_ann"].sum())
# 3-5 사각지대 셀
bl = cell[cell.blind]
res["n_blind_cells"] = int(len(bl)); res["n_cells"] = int(len(cell))
res["n_blind_dongs"] = int(bl.dong.nunique())
res["blind_extra_vkm_share"] = float((bl.extra_vkm * bl.ann_w).sum() / (cell.extra_vkm * cell.ann_w).sum())
# 3-5b 2×2
dg = cell.groupby("dong").agg(space_good=("space_good", "first"), has_blind=("blind", "any")).reset_index()
tab = pd.crosstab(dg.space_good, dg.has_blind)
res["2x2"] = {f"space_good={int(i)}|blind={bool(j)}": int(tab.loc[i, j]) for i in tab.index for j in tab.columns}
gb = bl[bl.space_good == 1]
res["n_dong_good_blind"] = int(gb.dong.nunique())
res["share_good_blind_among_good"] = res["n_dong_good_blind"] / int(dg.space_good.sum())
res["good_blind_cells"] = int(len(gb))
res["good_blind_trips_share_of_blind"] = float((gb.trips_out * gb.ann_w).sum() / (bl.trips_out * bl.ann_w).sum()) if len(bl) else 0.0
res["good_blind_extra_vkm_share_of_blind"] = float((gb.extra_vkm * gb.ann_w).sum() / (bl.extra_vkm * bl.ann_w).sum()) if len(bl) else 0.0
res["good_blind_extra_vkm_share_of_total"] = float((gb.extra_vkm * gb.ann_w).sum() / (cell.extra_vkm * cell.ann_w).sum())
res["blind_tbin_counts"] = bl.groupby(["daytype", "tbin"]).size().to_dict()
res["blind_tbin_counts"] = {f"{k[0]}|{k[1]}": int(v) for k, v in res["blind_tbin_counts"].items()}
res["good_blind_tbin_counts"] = {f"{k[0]}|{k[1]}": int(v) for k, v in gb.groupby(["daytype", "tbin"]).size().items()}
# 3-6(a) 집중곡선: 동을 65+ 비율 오름차순 정렬, 공백 노출 인구(인원×시간, 연간 가중) 누적
dn = cell.assign(expo_b=np.where(cell.blind, cell.expo.fillna(0) * cell.ann_w, 0.0), expo_all=cell.expo.fillna(0) * cell.ann_w) \
    .groupby("dong").agg(old_share=("old_share", "first"), pop=("pop", "first"), expo_b=("expo_b", "sum"), expo_all=("expo_all", "sum"),
                         space_good=("space_good", "first"), n_blind=("blind", "sum"), adm_nm=("adm_nm", "first")).reset_index()
dn = dn.sort_values("old_share").reset_index(drop=True)
def conc_index(df, w="pop"):
    # 집중지수 CI = 2·cov(h, r)/mean(h), r = 인구가중 분위 순위. h = 동별 1인당 노출(공백 노출/주민 인구)
    d = df.sort_values("old_share"); wts = d[w] / d[w].sum()
    r = wts.cumsum() - wts / 2
    h = d.expo_b / d[w]
    mu = np.average(h, weights=wts)
    return float(2 * np.average((h - mu) * (r - 0.5), weights=wts) / mu)
res["conc_index"] = conc_index(dn)
dn["cum_pop"] = dn["pop"].cumsum() / dn["pop"].sum()
dn["cum_expo_b"] = dn.expo_b.cumsum() / dn.expo_b.sum()
q20, q80 = dn.old_share.quantile(.2), dn.old_share.quantile(.8)
lo, hi = dn[dn.old_share <= q20], dn[dn.old_share >= q80]
res["expo_per_cap_low20"] = float(lo.expo_b.sum() / lo["pop"].sum())
res["expo_per_cap_high20"] = float(hi.expo_b.sum() / hi["pop"].sum())
res["blind_dong_share_low20"] = float((lo.n_blind > 0).mean()); res["blind_dong_share_high20"] = float((hi.n_blind > 0).mean())
if not QUIET: dn.to_csv(OUT / "03_동.csv", index=False, encoding="utf-8-sig")
if not QUIET:
    json.dump(res, open(OUT / "03_요약.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
    P(json.dumps(res, ensure_ascii=False, indent=1, default=float))
    P(by.round(3).to_string())
    (LOG / "03_analysis.txt").write_text(log.getvalue(), encoding="utf-8")
else:
    print(json.dumps({k: res[k] for k in ["x", "y", "space_t", "n_blind_cells", "n_blind_dongs", "n_dong_good_blind", "share_good_blind_among_good",
                                         "good_blind_extra_vkm_share_of_blind", "good_blind_trips_share_of_blind", "conc_index"]}, ensure_ascii=False, default=float))
