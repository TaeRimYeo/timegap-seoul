"""3-3 파업 1단계(a): OA-21220 2026-01 일별 운행횟수 → 파업일(01-13·14) vs 대조일(01-06·07·20·21) 및 1월 전체 일별 추이
출력: outputs/03_파업_버스운행_일별.csv"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).parent))
from common import *
import duckdb, zipfile, shutil, pandas as pd
con = duckdb.connect()
tmpd = TMP / "bus202601"; tmpd.mkdir(parents=True, exist_ok=True)
rows = []
with zipfile.ZipFile(EXT / "tpss_sta_route_hturn_202601.zip") as z:
    for n in z.namelist():
        z.extract(n, tmpd); u = to_utf8_tmp(tmpd / n); (tmpd / n).unlink()
        hs = " + ".join(f"coalesce(try_cast(h{h:02d} AS INT),0)" for h in range(24))
        df = con.execute(f"""SELECT date, count(DISTINCT route_id) routes, count(DISTINCT route_id) FILTER (WHERE ({hs})>0) routes_active,
                 sum({hs}) runs, sum({hs}) FILTER (WHERE stop_id LIKE '1%') runs_seoul_stops FROM {bus_csv_sql(u)} GROUP BY 1 ORDER BY 1""").fetchdf()
        u.unlink(); rows.append(df)
shutil.rmtree(tmpd, ignore_errors=True)
d = pd.concat(rows).sort_values("date")
d["dow"] = pd.to_datetime(d.date).dt.day_name()
d.to_csv(OUT / "03_파업_버스운행_일별.csv", index=False, encoding="utf-8-sig")
print(d.to_string())
