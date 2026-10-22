"""전체 파이프라인 실행 (번호순). 사용: python -I run_all.py [시작단계]
원자료는 data/raw/ 에, 에이전트 다운로드 자료는 data/external/ 에 있어야 한다(data/README.md 참조)."""
import subprocess, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent
STEPS = [
    ("00_profile", []), ("00_codecheck", None),
    ("01a_osm_stations", None),             # 이미 받은 경우 생략(None)
    ("01_supply", []),
    ("02a_od_extract", []), ("02b_panel", []), ("02c_equity", []),
    ("03_model", []), ("03b_bootstrap", ["200"]), ("03_analysis", []), ("03c_sensitivity", []), ("03f_equity_boot", []),
    ("03d_strike_stage1", []), ("02a_od_extract", ["20260106", "20260107", "20260113", "20260114", "20260120", "20260121"]), ("03e_strike", []), ("03h_strike_bands", []), ("03g_model_bands", []), ("03i_band_beta", ["200"]),
    ("04_carbon", []), ("04b_reallocation", []), ("04c_band_carbon", []), ("04b_reallocation", ["0.20", "band", "nopeak"]), ("05_modes", []),
    ("06_figures", []), ("07_app_data", []), ("08_report", []),
]
start = sys.argv[1] if len(sys.argv) > 1 else None
go = start is None
for name, args in STEPS:
    if not go:
        if name == start: go = True
        else: continue
    if args is None: continue
    t = time.time()
    print(f"== {name} {' '.join(args)}", flush=True)
    r = subprocess.run([sys.executable, "-I", str(ROOT / "src" / f"{name}.py"), *args])
    if r.returncode: sys.exit(f"실패: {name}")
    print(f"   {time.time()-t:.0f}s", flush=True)
