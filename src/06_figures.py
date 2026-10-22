"""Phase 6: 그림 1·2·3·4·5 (dpi 200, 폭 16cm 기준, Okabe-Ito 팔레트 — dataviz 검증 통과)"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).parent))
from common import *
import json, numpy as np, pandas as pd, geopandas as gpd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
try:
    import koreanize_matplotlib  # noqa
except Exception:
    pass
plt.rcParams.update({"axes.unicode_minus": False, "font.size": 8, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": "#e6e6e6", "grid.linewidth": 0.5, "axes.edgecolor": "#888", "axes.titlesize": 9,
                     "axes.titleweight": "bold", "savefig.dpi": 200, "savefig.bbox": "tight"})
VERM, BLUE, ORNG, GRN, GRAY, INK = "#D55E00", "#0072B2", "#E69F00", "#009E73", "#cfcfcf", "#333333"
CM = 1 / 2.54
SRC = "자료: 서울시 수도권 생활이동(OA-22657), 버스 운행횟수(OA-21220), 정류소 위치(OA-15067), 2026-09 분석일 10일"

cell = pd.read_parquet(OUT / "03_셀.parquet")
res = json.load(open(OUT / "03_요약.json", encoding="utf-8"))
carbon = json.load(open(OUT / "04_탄소.json", encoding="utf-8")) if (OUT / "04_탄소.json").exists() else None
g = gpd.read_file(EXT / "HangJeongDong_ver20260701.geojson"); g = g[g.sido == "11"].to_crs(5179); g["dong"] = g.adm_cd2.str[:8]
gu = g.dissolve("sggnm")

# ---------- 그림 1: 공간 × 시간 2×2 지도 ----------
dg = cell.groupby("dong").agg(space_good=("space_good", "first"), blind=("blind", "any")).reset_index()
wk1216 = set(cell[(cell.blind) & (cell.daytype == "wk") & (cell.tbin == "05-07")].dong)  # 심사 반영: 새벽 05–07 강조
dg["cls"] = np.select([(dg.space_good == 1) & dg.blind, (dg.space_good == 0) & dg.blind, (dg.space_good == 0) & ~dg.blind],
                      ["공간 양호·시간 사각지대", "공간 불량·시간 사각지대", "공간 불량·시간 양호"], "공간 양호·시간 양호")
m = g.merge(dg, on="dong")
colors = {"공간 양호·시간 사각지대": VERM, "공간 불량·시간 사각지대": ORNG, "공간 불량·시간 양호": BLUE, "공간 양호·시간 양호": "#eeeeee"}
fig, axes = plt.subplots(1, 2, figsize=(16 * CM, 7.6 * CM), gridspec_kw={"width_ratios": [1.25, 1]})
ax = axes[0]
for k, c in colors.items():
    sub = m[m.cls == k]
    sub.plot(ax=ax, color=c, edgecolor="white", linewidth=0.25)
gu.boundary.plot(ax=ax, color="#666", linewidth=0.4)
m[m.dong.isin(wk1216) & (m.space_good == 1)].boundary.plot(ax=ax, color="black", linewidth=0.9)
ax.set_axis_off()
n = dg.cls.value_counts()
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color=c, label=f"{k} ({n.get(k, 0)}개 동)") for k, c in colors.items()] +
          [Patch(facecolor="none", edgecolor="black", label="평일 05–07시 사각지대(공간 양호 동)")],
          loc="upper left", fontsize=7, frameon=False, bbox_to_anchor=(0.0, 0.0), ncol=2)
ax.set_title("서울시 기준(800m) 사각지대가 아닌데, 특정 시간엔 사각지대", loc="left")
# 오른쪽: 2×2 표
ax = axes[1]; ax.set_axis_off()
tab = pd.crosstab(dg.space_good.map({1: "공간 양호", 0: "공간 불량"}), dg.blind.map({True: "시간 사각지대 있음", False: "없음"}))
ax.text(0, 0.97, "행정동 2×2 분류 (427개 동)", fontsize=8, weight="bold", transform=ax.transAxes)
cells_txt = [("공간 양호", "시간 사각지대 있음", VERM), ("공간 양호", "없음", "#999"), ("공간 불량", "시간 사각지대 있음", ORNG), ("공간 불량", "없음", BLUE)]
for i, (r, c, col) in enumerate(cells_txt):
    x0, y0 = 0.05 + (i % 2) * 0.47, 0.55 - (i // 2) * 0.36
    ax.add_patch(plt.Rectangle((x0, y0), 0.44, 0.32, transform=ax.transAxes, facecolor=col, alpha=0.15, edgecolor=col))
    ax.text(x0 + 0.22, y0 + 0.2, f"{tab.loc[r, c]}", fontsize=16, weight="bold", ha="center", transform=ax.transAxes, color=INK)
    ax.text(x0 + 0.22, y0 + 0.06, f"{r}\n{c}", fontsize=6, ha="center", transform=ax.transAxes, color=INK)
ax.text(0.05, 0.08, f"공간 양호 동의 {res['share_good_blind_among_good']:.1%}가 시간 사각지대 셀 보유\n"
                    f"사각지대 셀 출발 통행의 {res['good_blind_trips_share_of_blind']:.0%}가 공간 양호 동에서 발생",
        fontsize=7.5, transform=ax.transAxes, color=INK)
fig.text(0, -0.13, "공간 양호: 동 면적의 50% 이상이 지하철역·중앙/가로변 버스전용차로 정류소 800m 안(서울시 ART와 정의가 완전히 같지 않음). "
         "시간 사각지대 셀(상대 개념): 그 시간대·요일 서울 동 공급 순위 하위 20% ∧ p75와의 공급 격차 상위 20% ∧ 출발통행 ≥50/일.\n" + SRC + "; 경계 vuski/admdongkor ver20260701",
         fontsize=6, color="#555", wrap=True)
fig.savefig(FIG / "그림1_공간시간_2x2지도.png"); plt.close(fig)

# ---------- 그림 2: 같은 OD 안의 시간 변동 — 잔차 binscatter + 모형 비교 ----------
from pyfixest.estimation import demean
pan = pd.read_parquet(INTERIM / "02_패널.parquet", columns=["o", "d", "tbin", "daytype", "car_share", "trips", "S_o", "S_d"])
fe = np.column_stack([pd.factorize(pan.o + pan.d)[0], pd.factorize(pan.tbin + pan.daytype)[0]]).astype(np.uint64)
X = pan[["car_share", "S_o", "S_d"]].to_numpy(float)
Xd, ok = demean(X, fe, pan.trips.to_numpy(float))
y, so, sd = Xd[:, 0], Xd[:, 1], Xd[:, 2]
w = pan.trips.to_numpy(float)
# FWL: S_d 를 추가로 제거
k1 = np.sum(w * sd * y) / np.sum(w * sd * sd); k2 = np.sum(w * sd * so) / np.sum(w * sd * sd)
yr, sr = y - k1 * sd, so - k2 * sd
qb = pd.qcut(sr, 20, labels=False, duplicates="drop")
bs = pd.DataFrame({"q": qb, "x": sr, "y": yr, "w": w}).groupby("q").apply(lambda z: pd.Series({"x": np.average(z.x, weights=z.w), "y": np.average(z.y, weights=z.w)}), include_groups=False)
slope = np.sum(w * sr * yr) / np.sum(w * sr * sr)
reg = pd.read_csv(OUT / "03_회귀표.csv"); stk = json.load(open(OUT / "03_파업.json", encoding="utf-8"))
fig, axes = plt.subplots(1, 2, figsize=(16 * CM, 6.8 * CM), gridspec_kw={"width_ratios": [1.15, 1]})
ax = axes[0]
ax.scatter(bs.x, bs.y * 100, s=18, color=VERM, zorder=3)
xx = np.linspace(bs.x.min(), bs.x.max(), 10); ax.plot(xx, slope * xx * 100, color=INK, lw=1)
ax.axhline(0, color="#999", lw=0.6); ax.axvline(0, color="#999", lw=0.6)
ax.set_xlabel("출발지 공급 S (OD·시간대×요일 평균 대비 편차, log)"); ax.set_ylabel("차량 비중 편차 (%p)")
ax.set_title("같은 OD 안 잔차: 기울기는 양 끝 분위에 크게 기댄다", loc="left", fontsize=8.5)
ax.text(0.98, 0.95, f"기울기 {slope*100:.1f}%p / log 1단위\n(통행 가중, 20분위 평균)", transform=ax.transAxes, ha="right", va="top", fontsize=6.5)
ax = axes[1]
lab = {"M1": "기본(시간대 공통)", "M2": "버스 공급만", "M3": "심야 제외(05–22)", "M4": "주말만", "M5": "평일만",
       "So_night": "심야 22–05 안 변동만", "So_dawn": "새벽 05–07 안 변동만", "So_day": "주간 07–22 안 변동만"}
rr = reg[reg["var"].isin(["S_o", "Sbus_o"])].copy(); rr["m"] = rr.model.str[:2]
b4 = pd.read_csv(OUT / "03_회귀표_시간대분리.csv"); b4 = b4[b4.model.str.startswith("B4") & b4["var"].str.startswith("So_")]
rr = pd.concat([rr[["m", "coef", "ci_lo", "ci_hi"]], pd.DataFrame({"m": b4["var"], "coef": b4.Estimate, "ci_lo": b4["2.5%"], "ci_hi": b4["97.5%"]})])
yy = np.arange(len(rr))[::-1]
colr = [BLUE if m.startswith("So_") else VERM for m in rr.m]
for k in range(len(rr)):
    r_ = rr.iloc[k]
    ax.errorbar(r_.coef * 100, yy[k], xerr=[[(r_.coef - r_.ci_lo) * 100], [(r_.ci_hi - r_.coef) * 100]], fmt="o", color=colr[k], ms=4, lw=1.2, capsize=2)
ax.set_yticks(yy); ax.set_yticklabels([lab[m] for m in rr.m], fontsize=7)
ax.axvline(0, color="#999", lw=0.8)
ax.set_xlabel("출발지 공급 계수 β_o (%p / log 1단위, 95% 구간)")
ax.set_title("시간대 안의 변동만 쓰면 심야만 음수로 남는다", loc="left", fontsize=8.5)
fig.text(0, -0.1, f"모형: 차량비중 ~ S_o + S_d | OD쌍 + 시간구간×요일 고정효과, 통행 가중, 출발 동 군집 표준오차 (N={int(reg.n.iloc[0]):,} OD×구간×요일). 연관이며 인과가 아님(시간대별 목적·동행 구성 등 남은 교란).\n" + SRC, fontsize=5.5, color="#555")
fig.tight_layout(); fig.savefig(FIG / "그림2_같은OD_다른시간.png"); plt.close(fig)
json.dump({"binscatter_slope": float(slope)}, open(OUT / "06_그림2.json", "w", encoding="utf-8"))

# ---------- 그림 4: 시간 구간별 추가 배출 — 시간대별 계수(막대) vs 시간대 공통 계수(윤곽, 상한 시나리오) ----------
order = TBINS[-1:] + TBINS[:-1]
by = pd.read_csv(OUT / "04c_구간별_배출.csv")          # 시간대별 계수(03i B4)
byc = pd.read_csv(OUT / "04_구간별_배출.csv")          # 시간대 공통 계수(M1)
cb = json.load(open(OUT / "04c_시간대별_탄소.json", encoding="utf-8"))
fig, ax = plt.subplots(figsize=(16 * CM, 6.8 * CM))
labels, xs = [], []
for j, dt in enumerate(["wk", "we"]):
    b = by[by.daytype == dt].set_index("tbin").reindex(order)
    bc = byc[byc.daytype == dt].set_index("tbin").reindex(order)
    pos = np.arange(8) + j * 9
    col = [VERM if t in ("22-24", "00-05", "05-07") else GRAY for t in order]
    ax.bar(pos, bc.tco2_ann, facecolor="none", edgecolor="#777", linestyle="--", lw=0.7, width=0.8)
    ax.bar(pos, b.tco2_ann, color=col, width=0.8)
    ax.errorbar(pos, b.tco2_ann, yerr=[b.tco2_ann - b.tco2_lo, b.tco2_hi - b.tco2_ann], fmt="none", ecolor=INK, lw=0.8, capsize=2)
    xs += list(pos); labels += [t for t in order]
ax.axhline(0, color="#555", lw=0.6)
ax.set_xticks(xs); ax.set_xticklabels(labels, fontsize=6.5, rotation=0)
ax.text(3.5, -0.2, "평일(화–목 패턴 × 연 245일)", ha="center", transform=ax.get_xaxis_transform(), fontsize=7.5)
ax.text(12.5, -0.2, "주말·공휴일(× 연 120일)", ha="center", transform=ax.get_xaxis_transform(), fontsize=7.5)
ax.set_ylabel("연간 연관 추가 배출 (tCO₂/년)")
ax.set_title(f"시간대별 계수로 보면 연관 배출은 심야·새벽(22–07시)에서만 식별된다: 연 {cb['band_nd']['기본']['t']:,.0f} t", loc="left")
ax.legend(handles=[Patch(color=VERM, label="심야·새벽 22–07시 (계수 유의 → 헤드라인)"), Patch(color=GRAY, label="주간 07–22시 (계수 비유의·반대 부호 → 합산 안 함)"),
                   Patch(facecolor="none", edgecolor="#777", linestyle="--", label="시간대 공통 계수 가정(상한 시나리오)")], fontsize=6.5, frameon=False, loc="upper right")
fig.text(0, -0.22, "막대 = 공급을 같은 시간대·요일 동 분포 p75(상위 25% 동 수준)로 올릴 때 줄어드는 차량 통행과 연관된 배출. 계수는 시간대(심야·새벽·주간)마다 그 시간대 안의 변동만으로 따로 추정.\n"
         "오차막대 = 출발 동 블록 부트스트랩 200회 95% 구간(재차 1.4, 우회 1.296, 125.2 g/km). 연관 기반 추정이며 인과 효과가 아님.\n" + SRC, fontsize=5.8, color="#555")
fig.savefig(FIG / "그림4_구간별_추가배출.png"); plt.close(fig)

# ---------- 그림 5: 65세 이상 비율 순 공백 노출 집중곡선 ----------
dn = pd.read_csv(OUT / "03_동.csv", dtype={"dong": str}).dropna(subset=["old_share"]).sort_values("old_share")
dn = dn[dn["pop"] > 0]
cp = np.r_[0, dn["pop"].cumsum() / dn["pop"].sum()]
ce = np.r_[0, dn.expo_b.cumsum() / dn.expo_b.sum()]
fig, axes = plt.subplots(1, 2, figsize=(16 * CM, 6.8 * CM), gridspec_kw={"width_ratios": [1, 1.1]})
ax = axes[0]
ax.plot([0, 1], [0, 1], color="#999", lw=1, ls="--", label="균등 분포")
ax.plot(cp, ce, color=VERM, lw=2, label="시간 사각지대 공백 노출")
ax.fill_between(cp, ce, cp, color=VERM, alpha=0.08)
ax.set_xlabel("누적 주민 인구 비율\n(65세 이상 비율 낮은 동 → 높은 동)"); ax.set_ylabel("누적 공백 노출 (인원×시간)")
ci_txt = f"집중지수 {res['conc_index']:.3f}"
if (OUT / "03_집중지수_부트.json").exists():
    cb = json.load(open(OUT / "03_집중지수_부트.json", encoding="utf-8")); ci_txt += f"\n(95% 구간 {cb['lo']:.3f}~{cb['hi']:.3f})"
ax.text(0.04, 0.80, ci_txt, transform=ax.transAxes, fontsize=7)
ax.legend(fontsize=6, frameon=False, loc="lower right")
ax.set_title("공백 노출은 고령 비율 높은 동으로 기운다", loc="left")
ax = axes[1]
vals = [res["expo_per_cap_low20"], res["expo_per_cap_high20"]]
ax.bar(["65세+ 비율\n하위 20% 동", "65세+ 비율\n상위 20% 동"], vals, color=[BLUE, VERM], width=0.55)
for i, v in enumerate(vals):
    ax.text(i, v, f"{v:,.0f}", ha="center", va="bottom", fontsize=8, weight="bold", color=INK)
ax.set_ylabel("주민 1인당 연간 공백 노출\n(생활인구 인원×시간 ÷ 주민 수)")
cb2 = json.load(open(OUT / "03_집중지수_부트.json", encoding="utf-8"))
ax.set_title(f"1인당 노출 {vals[1]/vals[0]:.1f}배 (95% 구간 {cb2['ratio_lo']:.1f}~{cb2['ratio_hi']:.1f}배)", loc="left", fontsize=8)
fig.text(0, -0.1, "공백 노출 = 시간 사각지대 셀(동×시간 구간×요일)의 생활인구(OA-14991, 2025-09) 인원×시간을 연간 일수로 가중 합산. 65세 이상 비율: 행정안전부 주민등록(2026-09).\n행정동 단위 생태학적 지표로 개인의 연령·취약성을 뜻하지 않음.", fontsize=5.5, color="#555")
fig.tight_layout(); fig.savefig(FIG / "그림5_공백노출_집중곡선.png"); plt.close(fig)

# ---------- 그림 3: 파업 이중차분 ----------
if (OUT / "03_파업.json").exists():
    s = json.load(open(OUT / "03_파업.json", encoding="utf-8"))
    pp = pd.read_parquet(INTERIM / "03_파업패널.parquet")
    pp["grp"] = pd.qcut(pp.bus_share_pre, 4, labels=["버스 의존 하위 25%", "2분위", "3분위", "버스 의존 상위 25%"])
    t = pp.groupby(["grp", "date"], observed=True).apply(lambda z: z.car.sum() / z.trips.sum(), include_groups=False).unstack()
    fig, axes = plt.subplots(1, 2, figsize=(16 * CM, 6 * CM))
    ax = axes[0]
    ch = s["stage1_change"]
    ks = ["일반버스", "광역버스", "지하철", "차량", "도보"]
    ax.barh(ks[::-1], [ch[k] * 100 for k in ks[::-1]], color=[GRN if ch[k] > 0 else VERM for k in ks[::-1]], height=0.55)
    for i, k in enumerate(ks[::-1]):
        ax.text(ch[k] * 100, i, f" {ch[k]*100:+.1f}%", va="center", ha="left" if ch[k] > 0 else "right", fontsize=7)
    ax.axvline(0, color="#666", lw=0.8); ax.set_xlabel("파업일 ÷ 대조일 - 1 (%)")
    ax.set_title("1단계: 파업일(1/13·14) 수단별 통행 변화", loc="left")
    ax.set_xlim(-25, 25)
    ax = axes[1]
    days = ["20260106", "20260107", "20260113", "20260114", "20260120", "20260121"]
    for grp, col in zip(t.index, [BLUE, "#7aa6c9", "#e8a07a", VERM]):
        ax.plot([d[4:6] + "/" + d[6:] for d in days], t.loc[grp, days] * 100, marker="o", ms=3, lw=1.6 if "25%" in grp else 0.9, color=col, label=grp)
    ax.axvspan(1.5, 3.5, color="#999", alpha=0.12, lw=0)
    ax.set_ylabel("출발 동 차량 비중 (%)"); ax.legend(fontsize=5.5, frameon=False, ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    did = s["did_car_share"]
    ax.set_title(f"2단계: 버스 의존 동일수록 차량 비중이 덜 줄었다\n(DiD {did['coef']*100:+.1f}%p / 버스 비중 1단위, 95% {did['lo']*100:.1f}~{did['hi']*100:.1f})", loc="left", fontsize=7.5)
    fig.text(0, -0.22, "대조일 1/6·7·20·21(같은 요일), 파업일 1/13·14. 동시 조치(지하철 172회 증회·막차 연장, 무료 셔틀 670대)가 있어 '외생 충격 하의 반응'으로 해석.\n자료: OA-22657 2026-01, OA-21220 2026-01", fontsize=5.5, color="#555")
    fig.tight_layout(); fig.savefig(FIG / "그림3_파업_이중차분.png"); plt.close(fig)
print("figures done:", sorted(p.name for p in FIG.glob("*.png")))
