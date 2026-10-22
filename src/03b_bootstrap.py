"""출발 동 블록 부트스트랩: 출발 동을 복원추출(같은 동이 여러 번 뽑히면 OD 고정효과를 복제본별로 분리)해 M1 재추정.
200회(시드 20261016), 4개 프로세스 병렬. 출력: outputs/03_부트스트랩.csv (b, beta_o, beta_d)"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).parent))
from common import *
import numpy as np, pandas as pd
from multiprocessing import Pool

B = int(sys.argv[1]) if len(sys.argv) > 1 else 200
SEED = 20261016

def init():
    global DF, GROUPS, ORIGS
    import pandas as pd
    DF = pd.read_parquet(INTERIM / "02_패널.parquet", columns=["o", "d", "tbin", "daytype", "car_share", "trips", "S_o", "S_d"])
    DF["od"] = DF.o + "_" + DF.d
    ORIGS = np.array(sorted(DF.o.unique()))
    GROUPS = {o: idx for o, idx in DF.groupby("o").indices.items()}

def one(b):
    import pyfixest as pf
    rng = np.random.default_rng(SEED + b)
    draw = rng.choice(ORIGS, size=len(ORIGS), replace=True)
    parts = []
    for k, o in enumerate(draw):
        x = DF.iloc[GROUPS[o]].copy(); x["od"] = x.od + f"#{k}"; x["cl"] = f"{o}#{k}"; parts.append(x)
    d = pd.concat(parts, ignore_index=True)
    m = pf.feols("car_share ~ S_o + S_d | od + tbin^daytype", data=d, weights="trips", vcov="iid")
    c = m.coef()
    return dict(b=b, beta_o=float(c["S_o"]), beta_d=float(c["S_d"]))

if __name__ == "__main__":
    out = OUT / "03_부트스트랩.csv"
    done = pd.read_csv(out) if out.exists() else pd.DataFrame(columns=["b", "beta_o", "beta_d"])
    todo = [b for b in range(B) if b not in set(done.b)]
    with Pool(4, initializer=init) as pool:
        for i, r in enumerate(pool.imap_unordered(one, todo)):
            done = pd.concat([done, pd.DataFrame([r])], ignore_index=True)
            if i % 10 == 0 or i == len(todo) - 1:
                done.to_csv(out, index=False); print(len(done), r, flush=True)
    done.to_csv(out, index=False)
    print(done[["beta_o", "beta_d"]].describe(percentiles=[.025, .5, .975]))
