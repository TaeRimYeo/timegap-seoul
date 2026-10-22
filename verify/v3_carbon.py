# ③ 심야·새벽(22–07시) 연관 추가 배출(기본 시나리오, tCO2/년): 시간대별 계수(03i B4), 주간 계수 0
import pandas as pd, numpy as np
b = pd.read_csv("outputs/03_회귀표_시간대분리.csv"); b = b[b.model.str.startswith("B4")].set_index("var").Estimate
p = pd.read_parquet("data/interim/02_패널.parquet").merge(pd.read_parquet("outputs/03_셀.parquet").groupby(["tbin", "daytype"]).p75.first().reset_index())
band = np.select([p.tbin.isin(["22-24", "00-05"]), p.tbin == "05-07"], ["night", "dawn"], "day")
bo = np.select([band == "night", band == "dawn"], [b.So_night, b.So_dawn], 0.0); bd = np.select([band == "night", band == "dawn"], [b.Sd_night, b.Sd_dawn], 0.0)
e = p.trips * (-bo * (p.p75 - p.S_o).clip(lower=0) - bd * (p.p75 - p.S_d).clip(lower=0))
e = np.where(e > p.car, p.car, e)  # 차량 통행 수 상한
pkm = (e * p.car_dist_km.fillna(p.dist_km) * p.daytype.map({"wk": 245, "we": 120})).sum()
print(round(pkm * 1.296 / 1.4 * 125.2 / 1e6))
