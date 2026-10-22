"""3-6(a) 보조: 집중지수·상하위 20% 1인당 노출비의 동 단위 부트스트랩 95% 구간(1,000회, 시드 고정)
+ 시간 사각지대 동 유형: 요일구분별 사각지대 구간 수 6~8개 = 상시형, 1~5개 = 시간형
출력: outputs/03_집중지수_부트.json"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).parent))
from common import *
import json, numpy as np, pandas as pd
dn = pd.read_csv(OUT / "03_동.csv", dtype={"dong": str}).dropna(subset=["old_share"])
dn = dn[dn["pop"] > 0]
def ci(d):
    d = d.sort_values("old_share"); w = d["pop"] / d["pop"].sum(); r = w.cumsum() - w / 2
    h = d.expo_b / d["pop"]; mu = np.average(h, weights=w)
    return 2 * np.average((h - mu) * (r - 0.5), weights=w) / mu
def ratio(d):
    q20, q80 = d.old_share.quantile(.2), d.old_share.quantile(.8)
    lo, hi = d[d.old_share <= q20], d[d.old_share >= q80]
    return (hi.expo_b.sum() / hi["pop"].sum()) / (lo.expo_b.sum() / lo["pop"].sum())
rng = np.random.default_rng(20261016)
B = [(ci(s), ratio(s)) for s in (dn.iloc[rng.integers(0, len(dn), len(dn))] for _ in range(1000))]
B = np.array(B)
cell = pd.read_parquet(OUT / "03_셀.parquet")
nb = cell.groupby(["dong", "daytype"]).blind.sum().reset_index()
nb = nb[nb.blind > 0]
nb["type"] = np.where(nb.blind >= 6, "상시형", "시간형")
dong_type = nb.groupby("dong").type.apply(lambda s: "상시형" if (s == "상시형").any() else "시간형")
sg = cell.groupby("dong").space_good.first()
res = dict(ci=ci(dn), lo=float(np.percentile(B[:, 0], 2.5)), hi=float(np.percentile(B[:, 0], 97.5)),
           ratio=ratio(dn), ratio_lo=float(np.percentile(B[:, 1], 2.5)), ratio_hi=float(np.percentile(B[:, 1], 97.5)),
           blind_dong_types=dong_type.value_counts().to_dict(),
           good_blind_types=dong_type[sg.reindex(dong_type.index) == 1].value_counts().to_dict(),
           blind_bins_per_daytype_median=float(nb.blind.median()))
json.dump(res, open(OUT / "03_집중지수_부트.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
print(res)
