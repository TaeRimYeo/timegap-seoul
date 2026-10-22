"""Phase 4b/5: P2 시간대 재배분 시뮬레이션 (운행 횟수·버스km 총량 불변)
같은 자치구·같은 요일구분에서 사각지대가 아닌 '기여 셀'(S > p75, 1회당 한계 효과가 작은 순)의 운행 일부(일 운행의 20%까지)를 시간 사각지대 셀로 옮긴다.
- 받는 셀: e^S → e^S + a (회/시), a = min(p75까지 필요한 양, 기여 셀 일 운행의 20% ÷ 받는 셀 시간 수 ÷ 받는 셀 수)
- 주는 셀: e^S_d → e^S_d − a·H_b/H_d  (일 운행 횟수 보존 → 버스km 불변)
- 차량 통행 변화 = (−β_o·T_out − β_d·T_in)·Δln(e^S)  (3-2 연관 계수 적용 시뮬레이션, 실제 효과 아님)
- 배출 = 인통행 × 셀 평균 차량 거리(직선) × 우회계수 ÷ 재차인원 × g/km × 연간 일수
출력: outputs/05_재배분.csv, outputs/05_재배분.json, outputs/05_우선순위_상위10.csv
"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).parent))
from common import *
import json, numpy as np, pandas as pd
PR = json.load(open(ROOT / "src" / "params.json", encoding="utf-8"))
G = PR["car_gco2_per_km"]["value"]; CF, CF_LO = PR["circuity"]["value"], PR["circuity"]["low"]
OCC, OCC_LO, OCC_HI = PR["occupancy"]["value"], PR["occupancy"]["low"], PR["occupancy"]["high"]
NWK, NWE = PR["annual_days"]["weekday"], PR["annual_days"]["weekend_holiday"]
SHARE = float(sys.argv[1]) if len(sys.argv) > 1 else 0.20
HOURS = {b: len(TBIN_HOURS[b]) for b in TBINS}
# 계수: 기본 = 시간대 공통(M1). "band" = 시간대별(03i B4: 심야·새벽은 추정값, 주간은 0 — 04c 주 결과와 같은 규칙)
BAND = len(sys.argv) > 2 and sys.argv[2] == "band"
NOPEAK = len(sys.argv) > 3 and sys.argv[3] == "nopeak"   # 첨두(07–09·16–19) 운행은 빼지 않음(혼잡 제약)
SUF = ("_시간대" if BAND else "") + ("_첨두제외" if NOPEAK else "")
NO_DONOR = ["22-24", "00-05", "05-07"] + (["07-09", "16-19"] if NOPEAK else [])
cell = pd.read_parquet(OUT / "03_셀.parquet")
if BAND:
    b4 = pd.read_csv(OUT / "03_회귀표_시간대분리.csv"); b4 = b4[b4.model.str.startswith("B4")].set_index("var").Estimate
    bnd = np.select([cell.tbin.isin(["22-24", "00-05"]), cell.tbin == "05-07"], ["night", "dawn"], "day")
    bo = np.select([bnd == "night", bnd == "dawn"], [b4["So_night"], b4["So_dawn"]], 0.0)
    bd = np.select([bnd == "night", bnd == "dawn"], [b4["Sd_night"], b4["Sd_dawn"]], 0.0)
else:
    reg = pd.read_csv(OUT / "03_회귀표.csv"); m1 = reg[reg.model.str.startswith("M1")].set_index("var")
    bo, bd = m1.loc["S_o", "coef"], m1.loc["S_d", "coef"]
cell["H"] = cell.tbin.map(HOURS)
cell["lvl"] = np.exp(cell.S)                     # 1 + 버스 + 3×열차 (회/시)
cell["w"] = -bo * cell.trips_out - bd * cell.trips_in   # 일 인통행 / ln 단위
mean_d = (cell.extra_vkm.sum() / cell.extra_trips.sum())
cell["cdist"] = np.where(cell.extra_trips > 0, cell.extra_vkm / cell.extra_trips.replace(0, np.nan), mean_d)
cell["cdist"] = cell.cdist.fillna(mean_d)
cell["marg"] = cell.w / cell.lvl * cell.cdist    # 1회/시 추가당 일 인·km 감소(한계)
rows = []
cell["gu"] = cell.dong.str[:5]
# 같은 자치구·같은 요일구분 안에서: 기여 셀 = 사각지대 아님 ∧ S > p75. 한계 효과가 큰 받는 셀부터, 한계 효과가 작은 기여 셀의 운행을 탐욕적으로 배정
for (gu, dt), grp in cell.groupby(["gu", "daytype"]):
    rec = grp[grp.blind].sort_values("marg", ascending=False)
    # 심야·새벽(22–07시) 운행은 줄이지 않는다(P3 대상 시간대·형평성)
    don = grp[(~grp.blind) & (grp.S > grp.p75) & (grp.bus_runs_h > 0) & ~grp.tbin.isin(NO_DONOR)].sort_values("marg").copy()
    if rec.empty or don.empty: continue
    don["cap"] = SHARE * don.bus_runs_h * don.H       # 기여 셀 일 운행의 SHARE
    don["lvl_now"] = don.lvl
    days = NWK if dt == "wk" else NWE
    for _, r in rec.iterrows():
        need_day = max(0.0, np.exp(r.p75) - r.lvl) * r.H
        got, lvl_r, loss = 0.0, r.lvl, 0.0
        donors = []
        step = max(need_day / 40, 0.5)  # 작은 단위로 옮기며 매번 한계 이득 > 한계 손실을 확인
        while need_day - got > 1e-9:
            avail = don[don.cap > 1e-9]
            if avail.empty: break
            mg = avail.w / avail.lvl_now * avail.cdist
            j = mg.idxmin()
            take = min(don.at[j, "cap"], need_day - got, step)
            ad = take / don.at[j, "H"]
            l = don.at[j, "w"] * (np.log(don.at[j, "lvl_now"]) - np.log(don.at[j, "lvl_now"] - ad)) * don.at[j, "cdist"]
            gch = r.w * (np.log(r.lvl + (got + take) / r.H) - np.log(r.lvl + got / r.H)) * r.cdist
            if l >= gch: break
            loss += l; don.at[j, "lvl_now"] -= ad; don.at[j, "cap"] -= take; got += take
            key = f"{don.at[j, 'dong']}:{don.at[j, 'tbin']}"
            if key not in donors: donors.append(key)
        a = got / r.H
        gain = r.w * (np.log(r.lvl + a) - np.log(r.lvl)) * r.cdist
        rows.append(dict(dong=r.dong, adm_nm=r.adm_nm, daytype=dt, tbin=r.tbin, donors=";".join(donors[:3]), n_donors=len(donors), space_good=r.space_good,
                         old_share=r.old_share, S=r.S, p75=r.p75, add_runs_h=a, moved_runs_day=got, moved_runs_yr=got * days,
                         trips_out=r.trips_out, expo=r.expo, gain_pkm_day=gain, loss_pkm_day=loss, net_pkm_yr=(gain - loss) * days))
R = pd.DataFrame(rows)
t = lambda pkm, occ, cf: pkm * cf / occ * G / 1e6
R["net_t"] = t(R.net_pkm_yr, OCC, CF); R["net_t_lo"] = t(R.net_pkm_yr, OCC_HI, CF_LO); R["net_t_hi"] = t(R.net_pkm_yr, OCC_LO, CF)
R["net_kg_per_run"] = R.net_t * 1000 / R.moved_runs_yr.replace(0, np.nan)
R = R.sort_values("net_t", ascending=False)
R.to_csv(OUT / f"05_재배분{SUF}.csv", index=False, encoding="utf-8-sig")
N = 20; top = R.head(N)
res = dict(share_of_donor=SHARE, cells=int(len(R)), cells_with_move=int((R.moved_runs_day > 0).sum()), neg_cells=int((R.net_t < 0).sum()),
           all_net_t={"보수": float(R.net_t_lo.sum()), "기본": float(R.net_t.sum()), "낙관": float(R.net_t_hi.sum())},
           topN=N, topN_net_t={"보수": float(top.net_t_lo.sum()), "기본": float(top.net_t.sum()), "낙관": float(top.net_t_hi.sum())},
           topN_moved_runs_yr=float(top.moved_runs_yr.sum()),
           topN_kg_per_run={"보수": float(top.net_t_lo.sum() * 1000 / top.moved_runs_yr.sum()), "기본": float(top.net_t.sum() * 1000 / top.moved_runs_yr.sum()),
                            "낙관": float(top.net_t_hi.sum() * 1000 / top.moved_runs_yr.sum())},
           all_kg_per_run=float(R.net_t.sum() * 1000 / R.moved_runs_yr.sum()), all_moved_runs_yr=float(R.moved_runs_yr.sum()),
           topN_nonnight=float((~top.tbin.isin(["22-24", "00-05"])).mean()), topN_space_good=float(top.space_good.mean()),
           topN_tbins=top.groupby(["daytype", "tbin"]).size().rename(lambda k: f"{k[0]}|{k[1]}" if isinstance(k, tuple) else k).to_dict())
res["topN_tbins"] = {f"{k[0]}|{k[1]}": int(v) for k, v in top.groupby(["daytype", "tbin"]).size().items()}
json.dump(res, open(OUT / f"05_재배분{SUF}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
R.head(10).to_csv(OUT / f"05_우선순위_상위10{SUF}.csv", index=False, encoding="utf-8-sig")
print(json.dumps(res, ensure_ascii=False, indent=1, default=float))
print(R.head(10)[["adm_nm", "daytype", "tbin", "donors", "space_good", "old_share", "add_runs_h", "moved_runs_yr", "net_t", "net_kg_per_run"]].round(3).to_string())
