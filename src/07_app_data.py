"""Phase 7: 프로토타입용 데이터 (동×8구간×2요일구분) → app/data/cells.json, app/data/dongs.geojson"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).parent))
from common import *
import json, numpy as np, pandas as pd, geopandas as gpd
cell = pd.read_parquet(OUT / "03_셀.parquet")
# 심사 대응(2026-10-22): 시간대별 계수 결과(04c, 05_재배분_시간대_첨두제외)를 화면에 쓴다
b2 = pd.read_csv(OUT / "04c_셀_보강.csv", dtype={"dong": str})
bo = b2[["dong", "daytype", "tbin", "net_cng_t_band", "ebus_be_band", "add_runs_h", "drt_net_band"]].rename(
    columns={"net_cng_t_band": "net_cng_t", "ebus_be_band": "ebus_breakeven_kwh_km", "drt_net_band": "net_drt_t"})
PR = json.load(open(ROOT / "src" / "params.json", encoding="utf-8"))
re = pd.read_csv(OUT / "05_재배분_시간대_첨두제외.csv", dtype={"dong": str})[["dong", "daytype", "tbin", "net_t", "net_kg_per_run", "moved_runs_yr"]].rename(columns={"net_t": "net_p2_t"})
et = pd.read_csv(OUT / "04c_셀_추가통행.csv", dtype={"dong": str})
c = cell.merge(bo, on=["dong", "daytype", "tbin"], how="left").merge(re, on=["dong", "daytype", "tbin"], how="left").merge(et, on=["dong", "daytype", "tbin"], how="left")
c["extra_trips"] = c.extra_trips_band.fillna(0)   # 시간대별 계수(주간 0) 기준
out = {}
for _, r in c.iterrows():
    d = out.setdefault(r.dong, {"nm": r.adm_nm.replace("서울특별시 ", ""), "good": int(r.space_good), "cov": round(float(r.cov_art), 3),
                                "old": round(float(r.old_share), 4), "pop": int(r["pop"]), "c": {}})
    k = f"{r.daytype}|{r.tbin}"
    rec = {"bus": round(float(r.bus_runs_h), 1), "sub": round(float(r.sub_trains_h), 1), "S": round(float(r.S), 3), "p75": round(float(r.p75), 3),
           "rel": round(float(np.exp(r.S) / np.exp(r.p75)), 3), "b": int(bool(r.blind)), "trips": round(float(r.trips_out)), "ex": round(float(r.extra_trips), 1),
           "expo": None if pd.isna(r.expo) else round(float(r.expo))}
    if not pd.isna(r.net_cng_t):
        rec.update({"cng": round(float(r.net_cng_t), 1), "drt": round(float(r.net_drt_t), 1), "be": round(float(r.ebus_breakeven_kwh_km), 3)})
    if not pd.isna(r.get("net_p2_t", np.nan)):
        rec.update({"p2": round(float(r.net_p2_t), 2), "p2k": None if pd.isna(r.net_kg_per_run) else round(float(r.net_kg_per_run), 3)})
    d["c"][k] = rec
meta = {"tbins": TBINS, "generated": "2026-10-16", "source": "서울 열린데이터광장 OA-22657·OA-21220·OA-15067·OA-14991, 행정안전부 주민등록, 분석일 2026-09 화~목 6일·토·일 4일",
        "note": "추가 통행·배출은 연관 기반 추정, 보강 순감축은 시뮬레이션"}
json.dump({"meta": meta, "dongs": out}, open(ROOT / "app" / "data" / "cells.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
g = gpd.read_file(EXT / "HangJeongDong_ver20260701.geojson"); g = g[g.sido == "11"].copy(); g["dong"] = g.adm_cd2.str[:8]
g = g.to_crs(5179); g["geometry"] = g.geometry.simplify(25); g = g.to_crs(4326)[["dong", "geometry"]]
(ROOT / "app" / "data" / "dongs.geojson").write_text(g.to_json(drop_id=True), encoding="utf-8")
import re as _re
txt = (ROOT / "app" / "data" / "dongs.geojson").read_text(encoding="utf-8")
txt = _re.sub(r"(\d+\.\d{5})\d+", r"\1", txt)
(ROOT / "app" / "data" / "dongs.geojson").write_text(txt, encoding="utf-8")
# file:// 로 열어도 되도록 JS 래퍼도 생성(서버 불필요)
(ROOT / "app" / "data" / "cells.js").write_text("window.CELLS=" + (ROOT / "app" / "data" / "cells.json").read_text(encoding="utf-8") + ";", encoding="utf-8")
(ROOT / "app" / "data" / "dongs.js").write_text("window.DONGS=" + txt + ";", encoding="utf-8")
for f in ("cells.json", "dongs.geojson", "cells.js", "dongs.js"):
    print(f, round((ROOT / "app" / "data" / f).stat().st_size / 1e6, 2), "MB")
