"""Phase 2c: 형평성·노출 지표 (행정동, 생태학적 지표)
- 65세 이상 비율: 행정안전부 주민등록 연령별 인구(2026-09-30)
- 생활인구: OA-14991 2025-09(주, 계절 일치) / 2026-07(비교). (동, 시, 요일구분) 평균 총생활인구.
  2025-09·2026-07 코드 → 2026년 OD 코드(427개) 대응: 같은 코드는 그대로, 바뀐 코드는 경계 면적 가중 배분
  (구 경계: vuski/admdongkor 해당 시점 버전)
출력: outputs/02_동지표.csv, data/interim/02_생활인구.parquet, outputs/logs/02c_equity.txt
"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).parent))
from common import *
import duckdb, io, zipfile, datetime, urllib.request, shutil
import pandas as pd, numpy as np, geopandas as gpd
log = io.StringIO()
def P(*a):
    print(*a, flush=True); print(*a, file=log)

g = gpd.read_file(EXT / "HangJeongDong_ver20260701.geojson"); g = g[g.sido == "11"].to_crs(5179)
g["dong"] = g.adm_cd2.str[:8]
new_codes = set(g.dong)

# ---- 65세 이상 비율 ----
u = to_utf8_tmp(EXT / "MOIS_행정동_성연령별_주민등록인구_20260930.csv")
mo = pd.read_csv(u, dtype=str); u.unlink()
mo = mo[mo.행정기관코드.str.startswith("11") & (mo.행정기관코드.str[5:8] != "000")].copy()
mo["dong"] = mo.행정기관코드.str[:8]
num = lambda c: pd.to_numeric(mo[c].str.replace(",", ""), errors="coerce")
old_cols = [c for c in mo.columns if c.endswith(("세남자", "세여자")) and c.split("세")[0].isdigit() and int(c.split("세")[0]) >= 65]
old_cols += [c for c in mo.columns if "이상" in c]
P("65세 이상 집계 컬럼 수", len(old_cols), old_cols[-4:])
mo["pop"] = num("계"); mo["pop65"] = sum(num(c).fillna(0) for c in old_cols)
mo["old_share"] = mo.pop65 / mo["pop"]
eq = mo[["dong", "읍면동명", "pop", "pop65", "old_share"]]
P("주민등록 서울 동", len(eq), "65+ 비율 분포", eq.old_share.describe().round(3).to_dict(), "서울 전체", round(eq.pop65.sum() / eq["pop"].sum(), 4))

# ---- 생활인구 ----
def old_boundary(ver):
    p = EXT / f"HangJeongDong_{ver}.geojson"
    if not p.exists():
        url = f"https://raw.githubusercontent.com/vuski/admdongkor/master/{ver}/HangJeongDong_{ver}.geojson"
        urllib.request.urlretrieve(url, p)
    b = gpd.read_file(p); b = b[b.adm_cd2.astype(str).str.startswith("11")].to_crs(5179); b["code"] = b.adm_cd2.astype(str).str[:8]; return b[["code", "geometry"]]

# 강북구 6개 동: 생활인구 코드(1130559x~1130563x)가 경계·ADMI 어느 버전에도 없어 순서대로 1:1 대응
#   (번1·번2·번3·수유1·수유2·수유3동; 2026 코드 11305595·603·608·615·625·635)
GANGBUK = {"11305590": "11305595", "11305600": "11305603", "11305606": "11305608",
           "11305610": "11305615", "11305620": "11305625", "11305630": "11305635"}

def crosswalk(codes, ver="ver20200101"):
    """생활인구 코드 → 2026 코드 면적 가중. 구 경계(ver)와 2026 경계를 겹쳐 2% 이상 겹치는 동에 배분.
    코드가 2026에도 있으면 1:1, 바뀐 코드만 같은 구 안에서 면적 배분."""
    b = old_boundary(ver).dissolve("code").reset_index()
    inter = gpd.overlay(b[b.code.isin(codes)], g[["dong", "geometry"]], how="intersection", keep_geom_type=True)
    inter["a"] = inter.area
    inter["w"] = inter.a / inter.groupby("code").a.transform("sum")
    rows = []
    for c in codes:
        if c in GANGBUK:
            rows.append((c, GANGBUK[c], 1.0)); continue
        x = inter[inter.code == c]
        if len(x) == 0:
            rows.append((c, c, 1.0) if c in new_codes else (c, None, 0.0)); continue
        if c in new_codes:  # 코드 유지 = 같은 동(경계 버전 간 한강 수면 처리 차이로 생기는 가짜 분할 방지)
            rows.append((c, c, 1.0)); continue
        x = x[(x.dong.str[:5] == c[:5])]  # 같은 자치구 안에서만 배분
        x = x.assign(w=x.a / x.a.sum()); x = x[x.w >= 0.02]
        for dd, ww in zip(x.dong, x.w / x.w.sum()):
            rows.append((c, dd, ww))
    cw = pd.DataFrame(rows, columns=["code", "dong", "w"]).dropna()
    split = cw[cw.w < 1].code.unique()
    P("대응표: 1:1 아닌 생활인구 코드", len(split), cw[cw.code.isin(split)].round(3).values.tolist())
    P("대응 안 된 2026 동", sorted(new_codes - set(cw.dong)))
    cw.to_csv(OUT / "02_생활인구_코드대응표.csv", index=False)
    return cw

def load_lp(src, ym, ver):
    con = duckdb.connect()
    if src.suffix == ".zip":
        tmpd = TMP / f"lp_{ym}"; tmpd.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(src) as z:
            n = [x for x in z.namelist() if x.lower().endswith(".csv")][0]; z.extract(n, tmpd); src2 = tmpd / n
    else:
        src2 = src; tmpd = None
    u = to_utf8_tmp(src2)
    lp = con.execute(f"""SELECT column00 AS date, try_cast(column01 AS INT) AS hour, column02 AS code, try_cast(column03 AS DOUBLE) AS pop
                         FROM read_csv('{u.as_posix()}', header=false, skip=1, all_varchar=true, null_padding=true)""").fetchdf()
    u.unlink()
    if tmpd: shutil.rmtree(tmpd, ignore_errors=True)
    P(ym, "행", len(lp), "코드", lp.code.nunique(), "일자", lp.date.min(), lp.date.max(), "pop 결측", lp["pop"].isna().sum())
    lp["dow"] = pd.to_datetime(lp.date, format="%Y%m%d").dt.dayofweek
    # 화~목(1,2,3) / 토·일(5,6). 공휴일 제외
    hol = set()  # 2025-09·2026-07 화~목·토·일 중 공휴일 없음(달력 확인)
    lp["daytype"] = np.select([lp.dow.isin([1, 2, 3]), lp.dow.isin([5, 6])], ["wk", "we"], "x")
    lp = lp[(lp.daytype != "x") & ~lp.date.isin(hol)]
    a = lp.groupby(["code", "daytype", "hour"], as_index=False)["pop"].mean()
    cw = crosswalk(sorted(a.code.unique()), ver)
    m = a.merge(cw, on="code"); m["pop"] *= m.w
    out = m.groupby(["dong", "daytype", "hour"], as_index=False)["pop"].sum()
    P(ym, "매핑 후 동", out.dong.nunique(), "/ 427; 매핑 전후 총합 비", round(out["pop"].sum() / a["pop"].sum(), 5))
    out["ym"] = ym
    return out

lp_main = load_lp(EXT / "LOCAL_PEOPLE_DONG_202509.zip", "202509", "ver20200101")
lp_cmp = load_lp(RAW / "형평성" / "LOCAL_PEOPLE_DONG_202607.csv", "202607", "ver20200101")
lp = pd.concat([lp_main, lp_cmp])
lp["tbin"] = lp.hour.map(hour_to_tbin)
lp.to_parquet(INTERIM / "02_생활인구.parquet", index=False)
cmpd = lp.pivot_table(index=["dong", "daytype", "hour"], columns="ym", values="pop").dropna()
P("2025-09 vs 2026-07 동×시 생활인구 상관", round(np.corrcoef(cmpd["202509"], cmpd["202607"])[0, 1], 4), "총합 비(2607/2509)", round(cmpd["202607"].sum() / cmpd["202509"].sum(), 4))

acc = pd.read_csv(OUT / "01_공간접근성.csv", dtype={"dong": str})
dong = acc.merge(eq, on="dong", how="left")
day_pop = lp_main[lp_main.daytype == "wk"].groupby("dong")["pop"].mean().rename("lp_wk_mean")
dong = dong.merge(day_pop, on="dong", how="left")
dong.to_csv(OUT / "02_동지표.csv", index=False, encoding="utf-8-sig")
P("동지표", dong.shape, "65+ 결측", dong.old_share.isna().sum())
(LOG / "02c_equity.txt").write_text(log.getvalue(), encoding="utf-8")
