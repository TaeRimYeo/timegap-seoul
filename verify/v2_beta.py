# ② 같은 OD 모형 출발지 계수 (M1)
import pandas as pd, pyfixest as pf
df = pd.read_parquet("data/interim/02_패널.parquet")
df["od"] = df.o + "_" + df.d
m = pf.feols("car_share ~ S_o + S_d | od + tbin^daytype", data=df, weights="trips", vcov={"CRV1": "o"})
print(m.coef().round(4).to_dict())
