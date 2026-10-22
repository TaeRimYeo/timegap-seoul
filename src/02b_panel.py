"""Phase 2b: OD 패널 (o, d, tbin 8, daytype 2) — 일평균 수단별 통행, 차량 비중, 공급 결합

정의
- 차량 비중 = 차량(8) ÷ (차량 + 일반버스(5) + 광역버스(4) + 지하철(6)). 도보(7)·항공/기차/고속버스(1~3)·기타(9) 제외.
- 차량 중 이동거리 500m 미만 행(mode 80)은 위치 오차로 제외.
- 같은 동 내부 통행(o = d)은 제외(출발·도착 공급이 같아 S_o·S_d 식별 불가, 도보 위주).
- 일평균: 화~목 6일 / 토·일 4일 합 ÷ 일수.  분석 일수 평균 총통행(분모 4수단) ≥ 20인 OD쌍만 유지.
출력: data/interim/02_패널.parquet, outputs/logs/02b_panel.txt
"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).parent))
from common import *
import duckdb, io, json
import numpy as np, pandas as pd, geopandas as gpd

MIN_TRIPS = float(sys.argv[1]) if len(sys.argv) > 1 else 20.0
log = io.StringIO()
def P(*a):
    print(*a); print(*a, file=log)

con = duckdb.connect(); con.execute("SET threads=8; SET memory_limit='8GB'")
files = ", ".join(f"'{(INTERIM / f'od_{d}.parquet').as_posix()}'" for d in ANALYSIS_DAYS)
wk = ", ".join(f"'{d}'" for d in WEEKDAYS)
con.execute(f"""CREATE TABLE od AS
    SELECT o, d, hour, mode, trips, dist_w, regexp_extract(filename, 'od_(\\d{{8}})', 1) AS date
    FROM read_parquet([{files}], filename=true)""")
P("원 행수", con.execute("SELECT count(*), sum(trips) FROM od").fetchone())
P("수단별 일평균 통행(서울 내부, 전체 OD)")
P(con.execute(f"""SELECT mode, sum(trips) FILTER (WHERE date IN ({wk}))/6 wk_daily, sum(trips) FILTER (WHERE date NOT IN ({wk}))/4 we_daily
                FROM od GROUP BY 1 ORDER BY 1""").fetchdf().round(0).to_string())
P("o=d 비중(4수단):", con.execute("SELECT sum(trips) FILTER (WHERE o=d)/sum(trips) FROM od WHERE mode IN (4,5,6,8)").fetchone())
tb = tbin_sql("hour")
con.execute(f"""CREATE TABLE p AS
  SELECT o, d, {tb} AS tbin, CASE WHEN date IN ({wk}) THEN 'wk' ELSE 'we' END AS daytype,
    sum(trips) FILTER (WHERE mode=8) AS car, sum(trips) FILTER (WHERE mode=5) AS bus, sum(trips) FILTER (WHERE mode=4) AS gbus,
    sum(trips) FILTER (WHERE mode=6) AS subway, sum(trips) FILTER (WHERE mode=7) AS walk, sum(trips) FILTER (WHERE mode=80) AS car_lt500,
    sum(trips) FILTER (WHERE mode IN (4,5,6,8)) AS trips,
    sum(dist_w) FILTER (WHERE mode IN (4,5,6,8)) AS dist_w, sum(dist_w) FILTER (WHERE mode=8) AS car_dist_w
  FROM od WHERE o <> d GROUP BY ALL""")
con.execute("""UPDATE p SET car=coalesce(car,0), bus=coalesce(bus,0), gbus=coalesce(gbus,0), subway=coalesce(subway,0),
               walk=coalesce(walk,0), car_lt500=coalesce(car_lt500,0), trips=coalesce(trips,0)""")
# 일평균
con.execute("""CREATE TABLE p2 AS SELECT o, d, tbin, daytype,
    car/nd car, bus/nd bus, gbus/nd gbus, subway/nd subway, walk/nd walk, car_lt500/nd car_lt500, trips/nd trips,
    dist_w/nullif(trips*nd,0)*nd/1000 AS dist_km, car_dist_w/nullif(car*nd,0)*nd/1000 AS car_dist_km
    FROM (SELECT *, CASE WHEN daytype='wk' THEN 6.0 ELSE 4.0 END nd FROM p)""")
# OD쌍 필터: 분석 10일 평균 일 총통행
con.execute("""CREATE TABLE keep AS SELECT o, d, sum(trips*CASE WHEN daytype='wk' THEN 6 ELSE 4 END)/10 AS od_daily FROM p2 GROUP BY 1,2""")
k = con.execute(f"SELECT count(*), count(*) FILTER (WHERE od_daily>={MIN_TRIPS}), sum(od_daily), sum(od_daily) FILTER (WHERE od_daily>={MIN_TRIPS}) FROM keep").fetchone()
P(f"OD쌍 {k[0]:,} 중 일평균 ≥{MIN_TRIPS}: {k[1]:,} ({k[1]/k[0]:.1%}), 통행 비중 {k[3]/k[2]:.1%}")
panel = con.execute(f"""SELECT p2.* FROM p2 JOIN keep USING(o,d) WHERE keep.od_daily >= {MIN_TRIPS} AND p2.trips > 0""").fetchdf()
panel["car_share"] = panel.car / panel.trips
P("패널 행", len(panel), "OD쌍", panel.groupby(["o", "d"]).ngroups)

# 공급 결합
sup = pd.read_parquet(OUT / "01_공급지표.parquet")
s = sup[["dong", "daytype", "tbin", "S", "S_bus", "bus_runs_h", "sub_trains_h"]]
panel = panel.merge(s.rename(columns={"dong": "o", "S": "S_o", "S_bus": "Sbus_o", "bus_runs_h": "bus_o", "sub_trains_h": "sub_o"}), on=["o", "daytype", "tbin"], how="left")
panel = panel.merge(s.rename(columns={"dong": "d", "S": "S_d", "S_bus": "Sbus_d", "bus_runs_h": "bus_d", "sub_trains_h": "sub_d"}), on=["d", "daytype", "tbin"], how="left")
P("공급 결합 결측 S_o/S_d:", panel.S_o.isna().sum(), panel.S_d.isna().sum())

# 동 중심점 직선거리와 생활이동 이동거리 비교(거리 성격 판정 근거)
g = gpd.read_file(EXT / "HangJeongDong_ver20260701.geojson")
g = g[g.sido == "11"].to_crs(5179)
cen = dict(zip(g.adm_cd2.str[:8], g.geometry.representative_point()))
od = panel[["o", "d"]].drop_duplicates()
od["crow_km"] = [cen[a].distance(cen[b]) / 1000 for a, b in zip(od.o, od.d)]
panel = panel.merge(od, on=["o", "d"])
w = panel.car > 0
r = (panel.loc[w, "car_dist_km"] * panel.loc[w, "car"]).sum() / (panel.loc[w, "crow_km"] * panel.loc[w, "car"]).sum()
P(f"차량 통행가중 이동거리 ÷ 동 대표점 직선거리 = {r:.3f}")
P("거리대 비교(차량 통행가중 평균 km):")
panel["dband"] = pd.cut(panel.crow_km, [0, 2, 5, 10, 20, 60], labels=["<2", "2-5", "5-10", "10-20", "20+"])
P(panel[w].groupby("dband", observed=True).apply(lambda x: pd.Series({"crow": np.average(x.crow_km, weights=x.car), "move": np.average(x.car_dist_km, weights=x.car)})).round(2).to_string())

panel.to_parquet(INTERIM / "02_패널.parquet", index=False)
P("저장", INTERIM / "02_패널.parquet", panel.shape)
P("구간·요일별 차량 비중(통행가중):")
P(panel.groupby(["daytype", "tbin"]).apply(lambda x: pd.Series({"trips": x.trips.sum(), "car_share": x.car.sum() / x.trips.sum(), "S_o": np.average(x.S_o, weights=x.trips)})).round(3).to_string())
(LOG / "02b_panel.txt").write_text(log.getvalue(), encoding="utf-8")
