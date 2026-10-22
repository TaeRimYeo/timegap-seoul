"""Phase 0: 원자료 구조 확인 (버스운행, 생활인구, 정류소, 지하철). 결과는 outputs/logs/00_profile.txt"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).parent))
from common import *
import duckdb, openpyxl, io, contextlib

buf = io.StringIO()
con = duckdb.connect()
def q(s):
    df = con.execute(s).fetchdf(); print(df.to_string(max_rows=80)); return df

with contextlib.redirect_stdout(buf):
    for f in sorted((RAW / "버스운행").glob("*.csv")):
        print(f"\n## 버스운행: {f.name}  ({f.stat().st_size/1e6:.1f}MB, 수정 {f.stat().st_mtime})")
        u = to_utf8_tmp(f)
        con.execute(f"CREATE OR REPLACE TABLE b AS SELECT * FROM {bus_csv_sql(u)}")
        u.unlink()
        q("SELECT date, count(*) n_rows, count(distinct route_id) routes, count(distinct stop_id) stops, sum(try_cast(total as int)) total_runs FROM b GROUP BY 1 ORDER BY 1")
        hs = " + ".join(f"coalesce(try_cast(h{h:02d} as int),0)" for h in range(24))
        q(f"SELECT count(*) FILTER (WHERE try_cast(total as int) <> {hs}) total_ne_hoursum, count(*) FILTER (WHERE h10='') blank_h10, count(*) FILTER (WHERE h10<>'' AND try_cast(h10 as int) IS NULL) nonnum_h10 FROM b")
        q("SELECT substr(stop_id,1,3) pfx, count(distinct stop_id) n FROM b GROUP BY 1 ORDER BY 2 DESC LIMIT 10")
    lp = RAW / "형평성" / "LOCAL_PEOPLE_DONG_202607.csv"
    print(f"\n## 생활인구: {lp.name} ({lp.stat().st_size/1e6:.1f}MB)")
    u = to_utf8_tmp(lp)
    con.execute(f"CREATE TABLE lp AS SELECT * FROM read_csv('{u.as_posix()}', all_varchar=true, header=true)")
    u.unlink()
    print(con.execute("DESCRIBE lp").fetchdf().column_name.tolist())
    cols = con.execute("DESCRIBE lp").fetchdf().column_name.tolist()
    q(f'SELECT count(*) n, count(distinct "{cols[2]}") n_dong, min("{cols[0]}") d0, max("{cols[0]}") d1, count(distinct "{cols[1]}") n_hour, min("{cols[2]}") c0, max("{cols[2]}") c1, count(*) FILTER (WHERE try_cast("{cols[3]}" as double) IS NULL) nonnum_total FROM lp')
    q(f'SELECT * FROM lp LIMIT 2')
    print("\n## 정류소 xlsx")
    wb = openpyxl.load_workbook(RAW / "버스정류소" / "서울시버스정류소위치정보(20260902).xlsx", read_only=True)
    for ws in wb:
        rows = list(ws.iter_rows(values_only=True))
        print(ws.title, "rows", len(rows)); [print(r) for r in rows[:4]]
        types = {}
        for r in rows[1:]:
            types[r[-1] if len(r) else None] = types.get(r[-1] if len(r) else None, 0) + 1
        print("마지막 컬럼 값 분포(상위):", sorted(types.items(), key=lambda x: -x[1])[:10])
    print("\n## 지하철 열차운행현황")
    print((RAW / "지하철" / "서울교통공사_열차운행현황_20240331.csv").read_bytes().decode("cp949", errors="replace"))
(LOG / "00_profile.txt").write_text(buf.getvalue(), encoding="utf-8")
print(buf.getvalue())
