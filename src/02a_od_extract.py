"""Phase 2a: 생활이동 OD×수단 일별 zip → 서울 내부 OD 집계 parquet (하루씩 처리, 임시 CSV 삭제)

출력
- data/interim/od_YYYYMMDD.parquet : o, d, hour(출발 시), mode, trips, dist_w(=Σcnt×거리m), time_w
    mode 80 = '차량' 중 이동거리 500m 미만 행(위치 오차로 분석 제외, 추적용으로 분리 보관)
- data/interim/odx_YYYYMMDD.parquet : 서울 출발·서울 밖 도착 (o, hour, mode, trips)
- outputs/logs/02a_od_extract.csv : 일자별 행 수·통행 합계·서울 내부 비율·비숫자 빈도
사용: python -I src/02a_od_extract.py [YYYYMMDD ...]  (생략 시 분석일 10일)
"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).parent))
from common import *
import duckdb, zipfile, shutil, time, csv

def zip_path(day):
    for base in (RAW / "생활이동_OD", EXT / "생활이동_OD"):
        p = base / f"seoul_trans_admdong3_final_{day}.zip"
        if p.exists(): return p
    raise FileNotFoundError(day)

def process(day):
    out = INTERIM / f"od_{day}.parquet"
    if out.exists():
        print(day, "skip (exists)"); return None
    t0 = time.time()
    tmpd = TMP / f"od_{day}"; tmpd.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path(day)) as z:
        name = [n for n in z.namelist() if n.endswith(".csv")][0]
        z.extract(name, tmpd)
    f = (tmpd / name).as_posix()
    con = duckdb.connect(); con.execute("SET threads=8; SET memory_limit='6GB'")
    try:
        con.execute(f"CREATE VIEW raw AS SELECT * FROM read_csv('{f}', all_varchar=true, header=true)")
        con.execute("""CREATE TABLE r AS SELECT o_admdong_cd o, d_admdong_cd d,
                try_cast(substr(st_time_cd,1,2) AS INT) AS hour, try_cast(move_trans AS INT) mode0,
                try_cast(move_dist AS DOUBLE) dist, try_cast(move_time AS DOUBLE) mtime, try_cast(cnt AS DOUBLE) cnt,
                cnt raw_cnt FROM raw""")
    except Exception:
        # utf-8 실패 시 cp949 → utf-8 사본으로 재시도
        u = to_utf8_tmp(Path(f)); f = u.as_posix()
        con.execute(f"CREATE OR REPLACE VIEW raw AS SELECT * FROM read_csv('{f}', all_varchar=true, header=true)")
        con.execute("""CREATE OR REPLACE TABLE r AS SELECT o_admdong_cd o, d_admdong_cd d,
                try_cast(substr(st_time_cd,1,2) AS INT) AS hour, try_cast(move_trans AS INT) mode0,
                try_cast(move_dist AS DOUBLE) dist, try_cast(move_time AS DOUBLE) mtime, try_cast(cnt AS DOUBLE) cnt,
                cnt raw_cnt FROM raw""")
    st = con.execute("""SELECT count(*) n, sum(cnt) tot,
            count(*) FILTER (WHERE cnt IS NULL) cnt_null, count(*) FILTER (WHERE dist IS NULL) dist_null,
            count(*) FILTER (WHERE hour IS NULL) hour_null, count(*) FILTER (WHERE mode0 IS NULL) mode_null,
            count(*) FILTER (WHERE o LIKE '11%' AND d LIKE '11%') n_in, sum(cnt) FILTER (WHERE o LIKE '11%' AND d LIKE '11%') tot_in,
            sum(cnt) FILTER (WHERE o LIKE '11%' AND d LIKE '11%' AND mode0=8 AND dist<500) car_short
            FROM r""").fetchone()
    con.execute(f"""COPY (SELECT o, d, hour, CASE WHEN mode0=8 AND dist<500 THEN 80 ELSE mode0 END AS mode,
            sum(cnt) trips, sum(cnt*dist) dist_w, sum(cnt*mtime) time_w
            FROM r WHERE o LIKE '11%' AND d LIKE '11%' AND cnt IS NOT NULL AND hour IS NOT NULL
            GROUP BY ALL) TO '{out.as_posix()}' (FORMAT parquet, COMPRESSION zstd)""")
    con.execute(f"""COPY (SELECT o, hour, mode0 AS mode, sum(cnt) trips FROM r
            WHERE o LIKE '11%' AND d NOT LIKE '11%' AND cnt IS NOT NULL GROUP BY ALL)
            TO '{(INTERIM / f'odx_{day}.parquet').as_posix()}' (FORMAT parquet)""")
    nout = con.execute(f"SELECT count(*), sum(trips) FROM '{out.as_posix()}'").fetchone()
    con.close()
    shutil.rmtree(tmpd, ignore_errors=True)
    row = dict(day=day, rows=st[0], trips=st[1], cnt_null=st[2], dist_null=st[3], hour_null=st[4], mode_null=st[5],
               rows_seoul_internal=st[6], trips_seoul_internal=st[7], share_internal=st[7] / st[1],
               car_lt500_trips=st[8], out_rows=nout[0], out_trips=nout[1], sec=round(time.time() - t0, 1))
    print(row, flush=True)
    return row

if __name__ == "__main__":
    days = sys.argv[1:] or ANALYSIS_DAYS
    logf = LOG / "02a_od_extract.csv"
    for day in days:
        row = process(day)
        if row:
            new = not logf.exists()
            with open(logf, "a", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=list(row));
                if new: w.writeheader()
                w.writerow(row)
