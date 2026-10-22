"""3-2 보조: 시간대별 계수 — β가 어느 시간 변동에서 식별되는지 점검
car_share ~ S_o:band + S_d:band | od + tbin^daytype  (band: 심야 22–05 / 새벽 05–07 / 주간 07–22)
그리고 요일 축: OD×구간 고정효과로 평일·주말 대비만 사용
출력: outputs/03_회귀표_시간대별.csv"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).parent))
from common import *
import pandas as pd, numpy as np, pyfixest as pf
df = pd.read_parquet(INTERIM / "02_패널.parquet", columns=["o", "d", "tbin", "daytype", "car_share", "trips", "S_o", "S_d"])
df["od"] = df.o + "_" + df.d
band = np.select([df.tbin.isin(["22-24", "00-05"]), df.tbin == "05-07"], ["night", "dawn"], "day")
rows = []
for b in ["night", "dawn", "day"]:
    df[f"So_{b}"] = df.S_o * (band == b); df[f"Sd_{b}"] = df.S_d * (band == b)
m = pf.feols("car_share ~ So_night + So_dawn + So_day + Sd_night + Sd_dawn + Sd_day | od + tbin^daytype", data=df, weights="trips", vcov={"CRV1": "o"})
t = m.tidy(); t["model"] = "B1 시간대별 β (od + tbin×요일)"; rows.append(t)
df["odt"] = df.od + "_" + df.tbin
m2 = pf.feols("car_share ~ S_o + S_d | odt + tbin^daytype", data=df, weights="trips", vcov={"CRV1": "o"})
t = m2.tidy(); t["model"] = "B2 요일 축만 (od×구간 + 구간×요일)"; rows.append(t)
day = df[band == "day"]
m3 = pf.feols("car_share ~ S_o + S_d | odt + tbin^daytype", data=day, weights="trips", vcov={"CRV1": "o"})
t = m3.tidy(); t["model"] = "B3 요일 축, 주간(07–22)만"; rows.append(t)
out = pd.concat(rows).reset_index().rename(columns={"Coefficient": "var"})
out.to_csv(OUT / "03_회귀표_시간대별.csv", index=False, encoding="utf-8-sig")
print(out[["model", "var", "Estimate", "Std. Error", "Pr(>|t|)"]].round(4).to_string())
