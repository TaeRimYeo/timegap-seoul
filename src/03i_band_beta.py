"""3-2 수정(심사 대응): 시간대별 계수를 '그 시간대 안의 변동만'으로 따로 추정
car_share ~ S_o:band + S_d:band | od^band + tbin^daytype   (band: 심야 22–05 / 새벽 05–07 / 주간 07–22)
- od^band 고정효과 → 심야와 주간의 수준 차이는 계수 식별에 쓰이지 않는다(03g B1과 다른 점).
- 출발 동 블록 부트스트랩(시드 20261016, 03b와 같은 방식).
보조: 파업 DiD를 차량 '통행 수'(log)로 — 낮 시간 차량 통행이 실제로 늘었는지 점검.
출력: outputs/03_회귀표_시간대분리.csv, outputs/03_부트스트랩_시간대.csv, outputs/03_파업_차량통행.csv
"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).parent))
from common import *
import numpy as np, pandas as pd
from multiprocessing import Pool

B = int(sys.argv[1]) if len(sys.argv) > 1 else 200
SEED = 20261016
BANDS = ["night", "dawn", "day"]
FML = "car_share ~ " + " + ".join(f"So_{b} + Sd_{b}" for b in BANDS) + " | odb + tbin^daytype"

def load():
    df = pd.read_parquet(INTERIM / "02_패널.parquet", columns=["o", "d", "tbin", "daytype", "car_share", "trips", "S_o", "S_d"])
    df["band"] = np.select([df.tbin.isin(["22-24", "00-05"]), df.tbin == "05-07"], ["night", "dawn"], "day")
    for b in BANDS:
        df[f"So_{b}"] = df.S_o * (df.band == b); df[f"Sd_{b}"] = df.S_d * (df.band == b)
    df["odb"] = df.o + "_" + df.d + "_" + df.band
    return df

def init():
    global DF, GROUPS, ORIGS
    DF = load()
    ORIGS = np.array(sorted(DF.o.unique()))
    GROUPS = {o: idx for o, idx in DF.groupby("o").indices.items()}

def one(b):
    import pyfixest as pf
    rng = np.random.default_rng(SEED + b)
    draw = rng.choice(ORIGS, size=len(ORIGS), replace=True)
    parts = []
    for k, o in enumerate(draw):
        x = DF.iloc[GROUPS[o]].copy(); x["odb"] = x.odb + f"#{k}"; parts.append(x)
    m = pf.feols(FML, data=pd.concat(parts, ignore_index=True), weights="trips", vcov="iid")
    c = m.coef()
    return dict(b=b, **{k: float(c[k]) for k in c.index})

if __name__ == "__main__":
    import pyfixest as pf
    df = load()
    m = pf.feols(FML, data=df, weights="trips", vcov={"CRV1": "o"})
    t = m.tidy().reset_index().rename(columns={"Coefficient": "var"})
    t["model"] = "B4 시간대별 β, 시간대 안 변동만 (od×시간대 + 구간×요일)"
    # 주간을 더 쪼갠 판: 첨두 / 낮 비첨두 / 저녁 (각각 od×세부시간대 고정효과)
    sub = df[df.band == "day"].copy()
    sub["sb"] = np.select([sub.tbin.isin(["07-09", "16-19"]), sub.tbin.isin(["09-12", "12-16"])], ["peak", "mid"], "eve")
    rows = [t]
    for s in ["peak", "mid", "eve"]:
        x = sub[sub.sb == s]
        mm = pf.feols("car_share ~ S_o + S_d | od_ + tbin^daytype", data=x.assign(od_=x.o + "_" + x.d), weights="trips", vcov={"CRV1": "o"})
        tt = mm.tidy().reset_index().rename(columns={"Coefficient": "var"}); tt["model"] = f"B5 주간 세부({s}) 안 변동만"; rows.append(tt)
    out = pd.concat(rows)
    out.to_csv(OUT / "03_회귀표_시간대분리.csv", index=False, encoding="utf-8-sig")
    print(out[["model", "var", "Estimate", "Std. Error", "Pr(>|t|)", "2.5%", "97.5%"]].round(4).to_string())

    # 파업: 차량 통행 수(log) DiD, 시간대별
    pp = pd.read_parquet(INTERIM / "03_파업패널.parquet")
    pp = pp[pp.car > 0].assign(log_car=lambda x: np.log(x.car))
    rr = []
    for name, mask in {"전체": pp.tbin.notna(), "주간 07–22": ~pp.tbin.isin(["22-24", "00-05", "05-07"]), "평일 낮 비첨두 09–16": pp.tbin.isin(["09-12", "12-16"]),
                       "첨두 07–09·16–19": pp.tbin.isin(["07-09", "16-19"]), "심야·새벽 22–07": pp.tbin.isin(["22-24", "00-05", "05-07"])}.items():
        mm = pf.feols("log_car ~ treat | dong^tbin + date^tbin", data=pp[mask], weights="trips", vcov={"CRV1": "dong"})
        q = mm.tidy().iloc[0]
        rr.append(dict(band=name, y="log_car", coef=q["Estimate"], se=q["Std. Error"], p=q["Pr(>|t|)"], lo=q["2.5%"], hi=q["97.5%"], n=mm._N))
    rr = pd.DataFrame(rr); rr.to_csv(OUT / "03_파업_차량통행.csv", index=False, encoding="utf-8-sig"); print(rr.round(4).to_string())

    if B > 0:
        bo = OUT / "03_부트스트랩_시간대.csv"
        done = pd.read_csv(bo) if bo.exists() else pd.DataFrame(columns=["b"])
        todo = [b for b in range(B) if b not in set(done.b)]
        with Pool(4, initializer=init) as pool:
            for i, r in enumerate(pool.imap_unordered(one, todo)):
                done = pd.concat([done, pd.DataFrame([r])], ignore_index=True)
                if i % 20 == 0 or i == len(todo) - 1:
                    done.to_csv(bo, index=False); print(len(done), flush=True)
        done.to_csv(bo, index=False)
        print(done.drop(columns="b").describe(percentiles=[.025, .5, .975]).round(4).to_string())
