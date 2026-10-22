# ④ CNG 증회: 승용차 계수 3배·재차 1.2(시간대별 계수)에서도 순감축이 되는 사각지대 셀 수 / 전체 셀
import pandas as pd
c = pd.read_csv("outputs/04c_셀_보강.csv", dtype={"dong": str})
bus_t = c.bus_km_yr * 1.1999 / 1000                    # CNG 1.200 kgCO2/km
avoid = c.avoided_t_band * 3 * (1.4 / 1.2)             # 기본(125.2 g/km, 재차 1.4) → 3배, 재차 1.2
print(int((avoid > bus_t).sum()), len(c))
