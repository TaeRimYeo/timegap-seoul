"""Phase 3-2: 같은 길, 다른 시간 — OD 고정효과 + 구간×요일 고정효과 가중 회귀 (연관)
car_share ~ S_o + S_d | od + tbin^daytype, weights=trips, CRV1(o)
출력: outputs/03_회귀표.csv, outputs/logs/03_model.txt
"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).parent))
from common import *
import pandas as pd, numpy as np, pyfixest as pf, io, time
log = io.StringIO()
def P(*a):
    print(*a, flush=True); print(*a, file=log)
df = pd.read_parquet(INTERIM / "02_패널.parquet")
df["od"] = df.o + "_" + df.d
t0 = time.time()
specs = {
    "M1 기본 (S_o+S_d | od + tbin^daytype)": "car_share ~ S_o + S_d | od + tbin^daytype",
    "M2 버스만 (Sbus_o+Sbus_d)": "car_share ~ Sbus_o + Sbus_d | od + tbin^daytype",
    "M3 심야 제외(05-22)": "car_share ~ S_o + S_d | od + tbin^daytype",
    "M4 주말만": "car_share ~ S_o + S_d | od + tbin",
    "M5 평일만": "car_share ~ S_o + S_d | od + tbin",
}
rows = []
for name, f in specs.items():
    d = df
    if "심야 제외" in name: d = df[~df.tbin.isin(["22-24", "00-05"])]
    if "주말만" in name: d = df[df.daytype == "we"]
    if "평일만" in name: d = df[df.daytype == "wk"]
    m = pf.feols(f, data=d, weights="trips", vcov={"CRV1": "o"})
    t = m.tidy()
    for v in t.index:
        rows.append(dict(model=name, var=v, coef=t.loc[v, "Estimate"], se=t.loc[v, "Std. Error"], p=t.loc[v, "Pr(>|t|)"],
                         ci_lo=t.loc[v, "2.5%"], ci_hi=t.loc[v, "97.5%"], n=m._N, r2_within=getattr(m, "_r2_within", np.nan)))
    P(name, f"N={m._N}", t[["Estimate", "Std. Error", "Pr(>|t|)"]].round(4).to_dict("index"), f"{time.time()-t0:.0f}s")
res = pd.DataFrame(rows)
res.to_csv(OUT / "03_회귀표.csv", index=False, encoding="utf-8-sig")
(LOG / "03_model.txt").write_text(log.getvalue(), encoding="utf-8")
