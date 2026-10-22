# ① 공간 양호 동 중 시간 사각지대 셀 보유 동 수와 비율
import pandas as pd
c = pd.read_parquet("outputs/03_셀.parquet")
d = c.groupby("dong").agg(good=("space_good", "first"), blind=("blind", "any"))
n_good = int(d.good.sum()); n_gb = int((d.good.astype(bool) & d.blind).sum())
print(n_gb, n_good, round(n_gb / n_good * 100, 1))
