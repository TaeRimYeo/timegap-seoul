"""3-3 보조: 파업 이중차분을 시간대별로 (주간 07–22 / 심야·새벽) → outputs/03_파업_시간대별.csv"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).parent))
from common import *
import pandas as pd, numpy as np, pyfixest as pf
pp = pd.read_parquet(INTERIM / "03_파업패널.parquet")
rows = []
for name, mask in {"주간 07–22": ~pp.tbin.isin(["22-24", "00-05", "05-07"]), "평일 낮 비첨두 09–16": pp.tbin.isin(["09-12", "12-16"]),
                   "첨두 07–09·16–19": pp.tbin.isin(["07-09", "16-19"]), "심야·새벽 22–07": pp.tbin.isin(["22-24", "00-05", "05-07"])}.items():
    for y in ["car_share", "log_trips"]:
        m = pf.feols(f"{y} ~ treat | dong^tbin + date^tbin", data=pp[mask], weights="trips", vcov={"CRV1": "dong"})
        t = m.tidy().iloc[0]
        rows.append(dict(band=name, y=y, coef=t["Estimate"], se=t["Std. Error"], p=t["Pr(>|t|)"], lo=t["2.5%"], hi=t["97.5%"], n=m._N))
r = pd.DataFrame(rows); r.to_csv(OUT / "03_파업_시간대별.csv", index=False, encoding="utf-8-sig"); print(r.round(4).to_string())
