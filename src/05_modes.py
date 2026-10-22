"""Phase 5: 시간 사각지대 셀 보강 수단 비교 (같은 운행 횟수·같은 차량km 가정)
(a) CNG 버스 증회 1.200 kgCO2/km (b) DRT 승합차(가정: 125.2 g/km) (c) 전기버스: 손익분기 전비(kWh/km)
※ DRT의 수요응답 운행 특성(우회·공차)은 반영하지 못함 → 단순 비교. 시뮬레이션이며 실제 효과가 아님.
출력: outputs/05_수단비교.json, outputs/05_수단비교_구간별.csv"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).parent))
from common import *
import json, numpy as np, pandas as pd
PR = json.load(open(ROOT / "src" / "params.json", encoding="utf-8"))
c = pd.read_csv(OUT / "04_셀_보강.csv", dtype={"dong": str})
drt = PR["drt_gco2_per_km"]["value"] / 1000
c["net_drt_t"] = c.avoided_t - c.bus_km_yr * drt / 1000
c["night"] = c.tbin.isin(["22-24", "00-05", "05-07"])
g = c.groupby(["daytype", "tbin"]).agg(cells=("dong", "size"), avoided_t=("avoided_t", "sum"), cng_t=("bus_t_cng", "sum"), net_cng_t=("net_cng_t", "sum"),
                                      net_drt_t=("net_drt_t", "sum"), drt_pos=("net_drt_t", lambda s: int((s > 0).sum())),
                                      breakeven_med=("ebus_breakeven_kwh_km", "median"), trips_out_med=("trips_out", "median")).reset_index()
g.to_csv(OUT / "05_수단비교_구간별.csv", index=False, encoding="utf-8-sig")
res = dict(cells=int(len(c)), cng_neg=int((c.net_cng_t < 0).sum()), drt_pos=int((c.net_drt_t > 0).sum()), drt_pos_night=int(((c.net_drt_t > 0) & c.night).sum()),
           night_cells=int(c.night.sum()), breakeven_med_all=float(c.ebus_breakeven_kwh_km.median()),
           breakeven_med_night=float(c[c.night].ebus_breakeven_kwh_km.median()), breakeven_med_day=float(c[~c.night].ebus_breakeven_kwh_km.median()),
           breakeven_max=float(c.ebus_breakeven_kwh_km.max()), breakeven_p90=float(c.ebus_breakeven_kwh_km.quantile(.9)),
           cng_kg_per_added_run_med=float((c.net_cng_t * 1000 / c.add_runs_yr).median()),
           drt_kg_per_added_run_med=float((c.net_drt_t * 1000 / c.add_runs_yr).median()),
           drt_kg_per_added_run_night_med=float((c[c.night].net_drt_t * 1000 / c[c.night].add_runs_yr).median()),
           avoided_t_all=float(c.avoided_t.sum()), add_runs_yr_all=float(c.add_runs_yr.sum()), bus_t_cng_all=float(c.bus_t_cng.sum()))
json.dump(res, open(OUT / "05_수단비교.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1)); print(g.round(2).to_string())
