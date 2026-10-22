# ⑤ 파업일 서울 정류장 버스 운행 변화(대조일 1/6·7·20·21 대비)
import pandas as pd
d = pd.read_csv("outputs/03_파업_버스운행_일별.csv", dtype={"date": str}).set_index("date")
s = d.loc[["20260113", "20260114"], "runs_seoul_stops"].mean()
c = d.loc[["20260106", "20260107", "20260120", "20260121"], "runs_seoul_stops"].mean()
print(round((s / c - 1) * 100, 1))
