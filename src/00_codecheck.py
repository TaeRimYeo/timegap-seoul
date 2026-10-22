"""Phase 0: 코드 체계·매칭률 점검 → outputs/logs/00_codecheck.txt"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).parent))
from common import *
import duckdb, json, io, contextlib, openpyxl, zipfile

X = Path(sys.argv[1])  # 압축 해제된 OD CSV 1개(2026-09-08)
con = duckdb.connect()
buf = io.StringIO()
def q(s):
    df = con.execute(s).fetchdf(); print(df.to_string(max_rows=80)); return df
with contextlib.redirect_stdout(buf):
    g = json.load(open(EXT / "HangJeongDong_ver20260701.geojson", encoding="utf-8"))
    seoul = {f["properties"]["adm_cd2"][:8]: f["properties"]["adm_nm"] for f in g["features"] if f["properties"]["sido"] == "11"}
    print("경계(ver20260701) 서울 행정동 수:", len(seoul))
    con.execute(f"CREATE TABLE od AS SELECT * FROM read_csv('{X.as_posix()}', all_varchar=true)")
    od_codes = set(r[0] for r in con.execute("SELECT DISTINCT o_admdong_cd FROM od WHERE o_admdong_cd LIKE '11%' UNION SELECT DISTINCT d_admdong_cd FROM od WHERE d_admdong_cd LIKE '11%'").fetchall())
    print("OD 서울 코드 수:", len(od_codes), " 경계와 매칭:", len(od_codes & set(seoul)), " OD에만:", sorted(od_codes - set(seoul)), " 경계에만:", sorted(set(seoul) - od_codes))
    # 생활인구 코드
    u = to_utf8_tmp(RAW / "형평성" / "LOCAL_PEOPLE_DONG_202607.csv")
    lp_codes = set(r[0] for r in con.execute(f"SELECT DISTINCT column02 FROM read_csv('{u.as_posix()}', header=false, skip=1, all_varchar=true, null_padding=true)").fetchall())
    u.unlink()
    print("생활인구 202607 코드 수:", len(lp_codes), " OD 코드와 매칭:", len(lp_codes & od_codes), " 생활인구에만:", sorted(lp_codes - od_codes), " OD에만:", sorted(od_codes - lp_codes))
    # 주민등록 (10자리 행정기관코드)
    mo = EXT / "MOIS_행정동_성연령별_주민등록인구_20260930.csv"
    u = to_utf8_tmp(mo)
    con.execute(f"CREATE TABLE mo AS SELECT * FROM read_csv('{u.as_posix()}', all_varchar=true, header=true)"); u.unlink()
    mcodes = set(r[0][:8] for r in con.execute("SELECT 행정기관코드 FROM mo WHERE 행정기관코드 LIKE '11%' AND substr(행정기관코드,9,2)='00' AND substr(행정기관코드,6,3)<>'000'").fetchall())
    print("주민등록 서울 행정동 수:", len(mcodes), " OD와 매칭:", len(mcodes & od_codes), " 주민등록에만:", sorted(mcodes - od_codes), " OD에만:", sorted(od_codes - mcodes))
    # 수단별 서울 내부 통행 가중 거리·시간
    q("""SELECT move_trans, sum(cnt::double) trips, sum(move_dist::double*cnt::double)/sum(cnt::double) w_dist_m,
         sum(move_time::double*cnt::double)/sum(cnt::double) w_time_min,
         sum(move_dist::double*cnt::double)/nullif(sum(move_time::double*cnt::double),0)*0.06 kmh
         FROM od WHERE o_admdong_cd LIKE '11%' AND d_admdong_cd LIKE '11%' GROUP BY 1 ORDER BY 1""")
    q("SELECT in_forn_div_nm, sum(cnt::double) trips FROM od WHERE o_admdong_cd LIKE '11%' AND d_admdong_cd LIKE '11%' GROUP BY 1")
    q("SELECT count(*) same_od_rows, sum(cnt::double) FROM od WHERE o_admdong_cd=d_admdong_cd AND o_admdong_cd LIKE '11%'")
    # 정류소 ID ↔ 운행횟수 정류장_ID 매칭
    wb = openpyxl.load_workbook(RAW / "버스정류소" / "서울시버스정류소위치정보(20260902).xlsx", read_only=True)
    stops = {str(r[0]) for r in list(wb.active.iter_rows(values_only=True))[1:]}
    u = to_utf8_tmp(RAW / "버스운행" / "tpss_sta_route_hturn_2026.09.07-09.13.csv")
    con.execute(f"CREATE TABLE b AS SELECT * FROM {bus_csv_sql(u)}"); u.unlink()
    bs = con.execute("SELECT stop_id, coalesce(sum(try_cast(total as int)),0) runs FROM b GROUP BY 1").fetchall()
    tot = sum(r[1] for r in bs); hit = sum(r[1] for r in bs if r[0] in stops)
    print(f"운행 정류장 {len(bs)}개 중 좌표 매칭 {sum(r[0] in stops for r in bs)}개; 운행횟수 기준 매칭률 {hit/tot:.4f}")
    q("SELECT substr(stop_id,1,1) p1, count(DISTINCT stop_id) n, sum(try_cast(total as int)) runs, count(*) FILTER (WHERE try_cast(total as int) IS NULL) null_total FROM b GROUP BY 1 ORDER BY 1")
(LOG / "00_codecheck.txt").write_text(buf.getvalue(), encoding="utf-8")
print(buf.getvalue())
