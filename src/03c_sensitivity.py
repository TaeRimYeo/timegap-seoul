"""3-5 민감도: (x, y) ∈ {10,20,30}², 공간 양호 기준 30/50/70% → outputs/03_민감도.csv"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).parent))
from common import *
import subprocess, json, pandas as pd
rows = []
for st in (30, 50, 70):
    for x in (10, 20, 30):
        for y in (10, 20, 30):
            if st != 50 and (x, y) != (20, 20): continue
            r = subprocess.run([sys.executable, "-I", str(ROOT / "src" / "03_analysis.py"), str(x), str(y), str(st), "q"], capture_output=True, text=True, encoding="utf-8", errors="replace")
            line = [l for l in r.stdout.splitlines() if l.startswith("{")][-1]
            rows.append(json.loads(line)); print(rows[-1], flush=True)
pd.DataFrame(rows).to_csv(OUT / "03_민감도.csv", index=False, encoding="utf-8-sig")
