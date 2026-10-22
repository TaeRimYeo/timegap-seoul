"""Phase 1: 공급 지표(S_bus, S_sub, 통합 S)와 공간 접근성(ART 유사)

출력
- outputs/01_공급지표.parquet : dong, daytype(wk/we), hour(0~23) 및 tbin 단위
    bus_runs_h : 시간당 버스 운행횟수(노선 중복 제거: (노선,시) 동 내 정류소 최댓값을 노선별 합산), 분석일 평균
    sub_trains_h : 시간당 지하철 열차 수(역-노선 수 × 운행 여부 × 60/시격, 가정)
    S = log(1 + bus_runs_h + 3 × sub_trains_h)
- outputs/01_공간접근성.csv : 동별 면적, 800m 버퍼(지하철역 ∪ 중앙·가로변 버스전용차로 정류소) 피복률, 공간 양호(30/50/70%)
- outputs/logs/01_supply_log.txt
"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).parent))
from common import *
import duckdb, json, io, contextlib, math
import geopandas as gpd, pandas as pd, numpy as np
from shapely.geometry import Point

log = io.StringIO()
def P(*a):
    print(*a); print(*a, file=log)

# ---------- 행정동 경계 ----------
g = gpd.read_file(EXT / "HangJeongDong_ver20260701.geojson")
g = g[g["sido"] == "11"].copy()
g["dong"] = g["adm_cd2"].str[:8]
g = g[["dong", "adm_nm", "sggnm", "geometry"]].to_crs(5179)
g["area_km2"] = g.area / 1e6
P("서울 행정동", len(g))

# ---------- 버스 정류소 → 동 ----------
st = pd.read_excel(RAW / "버스정류소" / "서울시버스정류소위치정보(20260902).xlsx", dtype={"NODE_ID": str, "ARS_ID": str})
st.columns = ["stop_id", "ars", "name", "x", "y", "stype"]
st = gpd.GeoDataFrame(st, geometry=gpd.points_from_xy(st.x, st.y), crs=4326).to_crs(5179)
st = gpd.sjoin(st, g[["dong", "geometry"]], how="left", predicate="within").drop(columns="index_right")
P("정류소", len(st), "동 배정 실패", st.dong.isna().sum())
stop_dong = st.dropna(subset=["dong"])[["stop_id", "dong", "stype"]]

# ---------- 버스 운행횟수 (분석일만) ----------
con = duckdb.connect(); con.execute("SET threads=8")
con.register("stop_dong", stop_dong)
frames = []
for f in sorted((RAW / "버스운행").glob("tpss_sta_route_hturn_2026.09.*.csv")):
    if "09.21-09.27" in f.name:  # 추석 주간 제외(추가 지시 3)
        continue
    u = to_utf8_tmp(f)
    days = ",".join(f"'{d}'" for d in ANALYSIS_DAYS)
    hrs = ", ".join(f"h{h:02d}" for h in range(24))
    con.execute(f"""CREATE OR REPLACE TABLE b AS SELECT date, route_id, stop_id, {hrs} FROM {bus_csv_sql(u)} WHERE date IN ({days})""")
    u.unlink()
    # 정류소 매칭률(서울 정류소 = ID 앞자리 1)
    m = con.execute("""SELECT count(DISTINCT b.stop_id) FILTER (WHERE b.stop_id LIKE '1%') n1,
        count(DISTINCT b.stop_id) FILTER (WHERE b.stop_id LIKE '1%' AND s.stop_id IS NOT NULL) n1m
        FROM b LEFT JOIN stop_dong s USING(stop_id)""").fetchone()
    P(f.name, "서울(1xxxx) 정류장", m[0], "좌표·동 매칭", m[1], f"{m[1]/m[0]:.3%}")
    unp = " UNION ALL ".join(f"SELECT date, route_id, stop_id, {h} AS hour, coalesce(try_cast(h{h:02d} AS INT),0) runs FROM b" for h in range(24))
    df = con.execute(f"""WITH u AS ({unp})
        SELECT date, dong, hour, sum(mx) AS runs, count(*) AS n_routes FROM (
            SELECT u.date, s.dong, u.hour, u.route_id, max(u.runs) mx FROM u JOIN stop_dong s USING(stop_id)
            GROUP BY ALL HAVING max(u.runs) > 0) GROUP BY ALL""").fetchdf()
    frames.append(df)
bus = pd.concat(frames)
P("버스 일자", sorted(bus.date.unique()))
assert set(bus.date.unique()) == set(ANALYSIS_DAYS), "분석일 누락"
# 동×일×시 완전 격자 후 평균 (운행 0 포함)
grid = pd.MultiIndex.from_product([g.dong, ANALYSIS_DAYS, range(24)], names=["dong", "date", "hour"]).to_frame(index=False)
bus = grid.merge(bus, how="left", on=["dong", "date", "hour"]).fillna({"runs": 0, "n_routes": 0})
bus["daytype"] = np.where(bus.date.isin(WEEKDAYS), "wk", "we")
busd = bus.groupby(["dong", "daytype", "hour"], as_index=False).agg(bus_runs_h=("runs", "mean"), bus_routes_h=("n_routes", "mean"))

# ---------- 지하철 ----------
E = json.load(open(EXT / "osm_stations_seoul.json", encoding="utf-8"))["elements"]
rows = []
for e in E:
    if e["type"] != "node": continue
    t = e["tags"]
    if t.get("network") == "KTX": continue
    ops = [o for o in (t.get("operator") or "").split(";") if o]
    rows.append(dict(name=t.get("name"), operator=t.get("operator"), n_lines=max(1, len(ops)), lon=e["lon"], lat=e["lat"]))
sub = gpd.GeoDataFrame(pd.DataFrame(rows), geometry=gpd.points_from_xy([r["lon"] for r in rows], [r["lat"] for r in rows]), crs=4326).to_crs(5179)
sub = gpd.sjoin(sub, g[["dong", "geometry"]], how="left", predicate="within").drop(columns="index_right")
P("지하철 역 노드(KTX 제외)", len(sub), "역-노선 합", sub.n_lines.sum(), "동 배정 실패", sub.dong.isna().sum())
sub_in = sub.dropna(subset=["dong"]).groupby("dong").n_lines.sum()
# 기본(변경, 이유는 01_설명.md): 역 800m 안에 드는 동 면적 비율로 가중한 역-노선 수
#   = Σ_역 노선 수 × (동 면적 중 그 역 800m 버퍼 안 비율). 동 경계 밖 인접 역도 반영(ART 공간 기준과 정합).
# 'inside'(명세 원안): 동 안에 있는 역-노선 수
SUBWAY_MODE = sys.argv[1] if len(sys.argv) > 1 else "cover"
if SUBWAY_MODE == "inside":
    sub_cnt = sub_in
else:
    bufs = gpd.GeoDataFrame(sub[["n_lines"]].copy(), geometry=sub.geometry.buffer(800), crs=5179)
    ov = gpd.overlay(g[["dong", "geometry"]], bufs, how="intersection", keep_geom_type=True)
    ov["share"] = ov.area / ov.dong.map(g.set_index("dong").area)
    sub_cnt = (ov.n_lines * ov.share).groupby(ov.dong).sum()
P("지하철 공급 방식", SUBWAY_MODE, "역-노선 유효 수 합", round(float(sub_cnt.sum()), 1), "공급>0 동", int((sub_cnt > 0).sum()))

# 서울교통공사 1~8호선 시격(분): 열차운행현황_20240331 (2호선 본선 값 사용)
RH = [3, 2.5, 3, 2.5, 2.5, 4, 2.5, 4.5]
NH = [5, 5.5, 6.5, 5.5, 6.5, 8, 6, 8.5]
rh, nh = float(np.mean(RH)), float(np.mean(NH))
P(f"평균 시격 RH={rh:.3f}분, NH={nh:.3f}분 (1~8호선 단순평균; 타 운영기관 노선에도 가정 적용)")
def trains_per_hour(h, daytype):
    # 가정: 운행 05:30~익일 00:30 → 5시·0시는 절반, 1~4시 0. 평일 07~08·18~19시 첨두 시격, 그 외·주말 평시 시격
    if 1 <= h <= 4: return 0.0
    rate = 60 / (rh if (daytype == "wk" and h in (7, 8, 18, 19)) else nh)
    return rate * (0.5 if h in (0, 5) else 1.0)
subd = pd.MultiIndex.from_product([g.dong, ["wk", "we"], range(24)], names=["dong", "daytype", "hour"]).to_frame(index=False)
subd["n_station_lines"] = subd.dong.map(sub_cnt).fillna(0)
subd["sub_trains_h"] = [n * trains_per_hour(h, d) for n, h, d in zip(subd.n_station_lines, subd.hour, subd.daytype)]

sup = busd.merge(subd, on=["dong", "daytype", "hour"], how="right").fillna({"bus_runs_h": 0, "bus_routes_h": 0})
sup["tbin"] = sup.hour.map(hour_to_tbin)
W = 3.0  # 지하철 열차 1편 = 버스 3회 (가정; 1·5 민감도는 Tier 3)
sup["S"] = np.log1p(sup.bus_runs_h + W * sup.sub_trains_h)
# 구간 단위: 시간당 평균
tb = sup.groupby(["dong", "daytype", "tbin"], as_index=False).agg(bus_runs_h=("bus_runs_h", "mean"), sub_trains_h=("sub_trains_h", "mean"),
                                                                  n_station_lines=("n_station_lines", "first"))
tb["S"] = np.log1p(tb.bus_runs_h + W * tb.sub_trains_h)
tb["S_bus"] = np.log1p(tb.bus_runs_h)
sup.to_parquet(OUT / "01_공급지표_시간.parquet", index=False)
tb.to_parquet(OUT / "01_공급지표.parquet", index=False)
P("공급 구간표", tb.shape)
P(tb.groupby(["daytype", "tbin"]).agg(bus=("bus_runs_h", "median"), sub=("sub_trains_h", "median"), S=("S", "median"), S_p20=("S", lambda s: s.quantile(.2))).round(2).to_string())

# ---------- 공간 접근성 (ART 유사) ----------
lane = st[st.stype.isin(["중앙차로", "가로변전일", "가로변시간"])]
P("버스전용차로 근사 정류소", len(lane), lane.stype.value_counts().to_dict())
buf_sub = sub.geometry.buffer(800).union_all()
buf_lane = lane.geometry.buffer(800).union_all()
buf_all = buf_sub.union(buf_lane)
acc = g[["dong", "adm_nm", "sggnm", "area_km2"]].copy()
acc["cov_subway"] = g.geometry.intersection(buf_sub).area.values / g.area.values
acc["cov_lane"] = g.geometry.intersection(buf_lane).area.values / g.area.values
acc["cov_art"] = g.geometry.intersection(buf_all).area.values / g.area.values
for t in (30, 50, 70):
    acc[f"good{t}"] = (acc.cov_art >= t / 100).astype(int)
acc["n_station_lines"] = acc.dong.map(sub_in).fillna(0).astype(int)
acc["sub_lines_eff"] = acc.dong.map(sub_cnt).fillna(0).round(3)
acc["n_lane_stops"] = acc.dong.map(lane.groupby("dong").size()).fillna(0).astype(int)
acc.to_csv(OUT / "01_공간접근성.csv", index=False, encoding="utf-8-sig")
P("공간 양호 동 수(30/50/70%):", acc.good30.sum(), acc.good50.sum(), acc.good70.sum(), "/", len(acc))
P("피복률 분포", acc.cov_art.describe().round(3).to_dict())
(LOG / "01_supply_log.txt").write_text(log.getvalue(), encoding="utf-8")
