"""공통 경로·상수. 모든 스크립트는 `python -I src/<script>.py`로 실행한다."""
import sys, os, tempfile
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
EXT = ROOT / "data" / "external"
INTERIM = ROOT / "data" / "interim"
OUT = ROOT / "outputs"
FIG = ROOT / "figures"
LOG = ROOT / "outputs" / "logs"
for d in (INTERIM, OUT, FIG, LOG):
    d.mkdir(parents=True, exist_ok=True)

# 임시 해제 폴더: 프로젝트(OneDrive) 밖의 시스템 임시 폴더 사용
TMP = Path(tempfile.gettempdir()) / "timegap_tmp"

# 분석일 (달력 확인: 2026-09-08 화, 09-12 토)
WEEKDAYS = ["20260908", "20260909", "20260910", "20260915", "20260916", "20260917"]
WEEKENDS = ["20260912", "20260913", "20260919", "20260920"]
ANALYSIS_DAYS = WEEKDAYS + WEEKENDS

# 8개 시간 구간: 시작 시각(시) → 구간 라벨
TBINS = ["05-07", "07-09", "09-12", "12-16", "16-19", "19-22", "22-24", "00-05"]
def hour_to_tbin(h: int) -> str:
    if 5 <= h < 7: return "05-07"
    if 7 <= h < 9: return "07-09"
    if 9 <= h < 12: return "09-12"
    if 12 <= h < 16: return "12-16"
    if 16 <= h < 19: return "16-19"
    if 19 <= h < 22: return "19-22"
    if 22 <= h < 24: return "22-24"
    return "00-05"
TBIN_HOURS = {b: [h for h in range(24) if hour_to_tbin(h) == b] for b in TBINS}

# SQL CASE식(시: 정수 컬럼명 h)
def tbin_sql(h="h"):
    return (f"CASE WHEN {h} BETWEEN 5 AND 6 THEN '05-07' WHEN {h} BETWEEN 7 AND 8 THEN '07-09' "
            f"WHEN {h} BETWEEN 9 AND 11 THEN '09-12' WHEN {h} BETWEEN 12 AND 15 THEN '12-16' "
            f"WHEN {h} BETWEEN 16 AND 18 THEN '16-19' WHEN {h} BETWEEN 19 AND 21 THEN '19-22' "
            f"WHEN {h} BETWEEN 22 AND 23 THEN '22-24' ELSE '00-05' END")

# 수단 코드 (수도권 생활이동(수단별) 레이아웃.xlsx, 서울 열린데이터광장)
MODES = {1: "항공", 2: "기차", 3: "고속버스", 4: "광역버스", 5: "일반버스", 6: "지하철", 7: "도보", 8: "차량", 9: "기타"}

BUS_COLS = ["date", "route_id", "stop_id", "total"] + [f"h{h:02d}" for h in range(24)] + ["seq"]


def to_utf8_tmp(src: Path, enc_try=("utf-8", "cp949")) -> Path:
    """원본 CSV를 TMP 아래 UTF-8 사본으로 변환(스트리밍). 이미 UTF-8이면 그대로 복사."""
    TMP.mkdir(parents=True, exist_ok=True)
    dst = TMP / (src.stem + ".utf8.csv")
    with open(src, "rb") as f:
        head = f.read(1 << 20)
    enc = "cp949"
    try:
        head.decode("utf-8"); enc = "utf-8-sig"
    except UnicodeDecodeError as e:
        if e.start > len(head) - 4: enc = "utf-8-sig"
    with open(src, "r", encoding=enc, errors="replace", newline=None) as fi, open(dst, "w", encoding="utf-8", newline="") as fo:
        while True:
            chunk = fi.read(1 << 24)
            if not chunk: break
            fo.write(chunk)
    return dst


def bus_csv_sql(path: Path) -> str:
    """OA-21220 운행횟수 CSV(UTF-8 사본)를 스니핑 없이 모두 VARCHAR로 읽는 read_csv 식."""
    cols = "{" + ", ".join(f"'{c}': 'VARCHAR'" for c in BUS_COLS) + "}"
    return (f"read_csv('{path.as_posix()}', header=true, auto_detect=false, delim=',', "
            f"quote='\"', escape='\"', new_line='\\n', columns={cols})")
