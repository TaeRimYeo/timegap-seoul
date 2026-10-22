"""Phase 8: 분석보고서(docx → pdf). 공식 양식(분석보고서.pdf)의 표 항목 순서를 따른다.
모든 숫자는 outputs/ 결과 파일에서 읽어 넣고, 넣은 숫자마다 출처를 outputs/10_수치대조표.csv 에 기록한다.
"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).parent))
from common import *
import json, re, csv, subprocess
import pandas as pd, numpy as np
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

NAME = "여태림"
FILE_STEM = "여태림_분석보고서"
GITHUB = "https://github.com/TaeRimYeo/timegap-seoul"
TITLE = "같은 동네, 다른 시간: 지도에 없는 '시간 사각지대'가 만드는 차량 이동과 탄소"
REPORT = ROOT / "report"; REPORT.mkdir(exist_ok=True)

# ---------------- 숫자 등록(수치대조표) ----------------
LEDGER = []
def N(val, fmt, src, key):
    s = format(val, fmt)
    LEDGER.append(dict(key=key, text=s, value=val, source=src))
    return s
J = lambda f: json.load(open(OUT / f, encoding="utf-8"))
s3, c4, r5, m5, stk, eqb = J("03_요약.json"), J("04_탄소.json"), J("05_재배분.json"), J("05_수단비교.json"), J("03_파업.json"), J("03_집중지수_부트.json")
reg = pd.read_csv(OUT / "03_회귀표.csv"); regb = pd.read_csv(OUT / "03_회귀표_시간대별.csv"); stb = pd.read_csv(OUT / "03_파업_시간대별.csv")
sens = pd.read_csv(OUT / "03_민감도.csv"); boot = pd.read_csv(OUT / "03_부트스트랩.csv")
m1 = reg[reg.model.str.startswith("M1")].set_index("var"); m3 = reg[reg.model.str.startswith("M3")].set_index("var")
b2 = regb[regb.model.str.startswith("B2")].set_index("var")
sday = stb[(stb.band == "주간 07–22") & (stb.y == "car_share")].iloc[0]; sdayt = stb[(stb.band == "주간 07–22") & (stb.y == "log_trips")].iloc[0]
soff = stb[(stb.band == "평일 낮 비첨두 09–16") & (stb.y == "car_share")].iloc[0]
h1 = c4["headline1"]
tw = lambda x: x / 1e4  # 만 단위
# 심사 대응(2026-10-22): 시간대별 계수(03i)·시간대별 탄소와 CNG 민감도(04c)·시간대별 재배분(04b band nopeak)
cb, r5 = J("04c_시간대별_탄소.json"), J("05_재배분_시간대_첨두제외.json")
b4 = pd.read_csv(OUT / "03_회귀표_시간대분리.csv"); b4 = b4[b4.model.str.startswith("B4")].set_index("var")
stc = pd.read_csv(OUT / "03_파업_차량통행.csv").set_index("band")
cng = pd.read_csv(OUT / "04c_CNG_민감도.csv")
cng_pos = lambda beta, m, occ: int(cng[(cng.beta == beta) & (cng.car_mult == m) & (cng.occupancy == occ)].pos_cells.iloc[0])
nd = cb["band_nd"]

# 자주 쓰는 숫자
n_good = s3["2x2"]["space_good=1|blind=True"] + s3["2x2"]["space_good=1|blind=False"]
X = dict(
    good_blind=N(s3["n_dong_good_blind"], "d", "outputs/03_요약.json:n_dong_good_blind", "공간양호·시간사각 동 수"),
    n_good=N(n_good, "d", "outputs/03_요약.json:2x2", "공간 양호 동 수"),
    share_gb=N(s3["share_good_blind_among_good"] * 100, ".1f", "outputs/03_요약.json:share_good_blind_among_good", "공간양호 중 시간사각 비율(%)"),
    gb_vkm=N(s3["good_blind_extra_vkm_share_of_blind"] * 100, ".0f", "outputs/03_요약.json:good_blind_extra_vkm_share_of_blind", "사각 추가차량km 중 공간양호 몫(%)"),
    h1=N(tw(h1["기본"]["t"]), ".1f", "outputs/04_탄소.json:headline1.기본.t", "추가 배출 기본(만 t)"),
    h1lo=N(tw(h1["기본"]["ci_lo"]), ".1f", "outputs/04_탄소.json:headline1.기본.ci_lo", "추가 배출 95% 하한(만 t)"),
    h1hi=N(tw(h1["기본"]["ci_hi"]), ".1f", "outputs/04_탄소.json:headline1.기본.ci_hi", "추가 배출 95% 상한(만 t)"),
    h1min=N(tw(h1["보수"]["ci_lo"]), ".1f", "outputs/04_탄소.json:headline1.보수.ci_lo", "추가 배출 전체 범위 하한(만 t)"),
    h1max=N(tw(h1["낙관"]["ci_hi"]), ".1f", "outputs/04_탄소.json:headline1.낙관.ci_hi", "추가 배출 전체 범위 상한(만 t)"),
    nonnight=N(c4["share_nonnight"] * 100, ".0f", "outputs/04_탄소.json:share_nonnight", "심야 밖 비중(%)"),
    wk0916=N(c4["share_wk_0916"] * 100, ".0f", "outputs/04_탄소.json:share_wk_0916", "평일 09–16 비중(%)"),
    we=N(c4["share_weekend"] * 100, ".0f", "outputs/04_탄소.json:share_weekend", "주말 비중(%)"),
    p2top=N(r5["topN_net_t"]["기본"], ",.0f", "outputs/05_재배분_시간대_첨두제외.json:topN_net_t.기본", "재배분 상위20 순감축(t)"),
    p2toplo=N(r5["topN_net_t"]["보수"], ",.0f", "outputs/05_재배분_시간대_첨두제외.json:topN_net_t.보수", "재배분 상위20 하한(t)"),
    p2tophi=N(r5["topN_net_t"]["낙관"], ",.0f", "outputs/05_재배분_시간대_첨두제외.json:topN_net_t.낙관", "재배분 상위20 상한(t)"),
    p2all=N(r5["all_net_t"]["기본"], ",.0f", "outputs/05_재배분_시간대_첨두제외.json:all_net_t.기본", "재배분 전체 순감축(t)"),
    p2cells=N(r5["cells_with_move"], "d", "outputs/05_재배분_시간대_첨두제외.json:cells_with_move", "재배분 이동 셀 수"),
    p2neg=N(r5["neg_cells"], "d", "outputs/05_재배분_시간대_첨두제외.json:neg_cells", "재배분 음수 셀"),
    kgrun=N(r5["topN_kg_per_run"]["기본"], ".2f", "outputs/05_재배분_시간대_첨두제외.json:topN_kg_per_run.기본", "1회당 순감축(kg)"),
    kgrunlo=N(r5["topN_kg_per_run"]["보수"], ".2f", "outputs/05_재배분_시간대_첨두제외.json:topN_kg_per_run.보수", "1회당 하한"),
    kgrunhi=N(r5["topN_kg_per_run"]["낙관"], ".2f", "outputs/05_재배분_시간대_첨두제외.json:topN_kg_per_run.낙관", "1회당 상한"),
    cngneg=N(m5["cng_neg"], ",d", "outputs/05_수단비교.json:cng_neg", "CNG 증회 음수 셀"),
    cells=N(m5["cells"], ",d", "outputs/05_수단비교.json:cells", "사각지대 셀 수"),
    avoided=N(tw(m5["avoided_t_all"]), ".2f", "outputs/05_수단비교.json:avoided_t_all", "증회 회피 배출(만 t)"),
    busem=N(tw(m5["bus_t_cng_all"]), ".1f", "outputs/05_수단비교.json:bus_t_cng_all", "증회 버스 배출(만 t)"),
    drtpos=N(m5["drt_pos"], "d", "outputs/05_수단비교.json:drt_pos", "DRT 양(+) 셀"),
    be=N(m5["breakeven_med_all"], ".2f", "outputs/05_수단비교.json:breakeven_med_all", "전기버스 손익분기 전비 중앙"),
    bo=N(-m1.loc["S_o", "coef"] * 100, ".1f", "outputs/03_회귀표.csv:M1 S_o", "−β_o(%p), 높아지는 쪽 양수"),
    bd=N(-m1.loc["S_d", "coef"] * 100, ".1f", "outputs/03_회귀표.csv:M1 S_d", "−β_d(%p)"),
    bolo=N(-boot.beta_o.quantile(.975) * 100, ".1f", "outputs/03_부트스트랩.csv:beta_o q2.5", "β_o 부트 하한"),
    bohi=N(-boot.beta_o.quantile(.025) * 100, ".1f", "outputs/03_부트스트랩.csv:beta_o q97.5", "β_o 부트 상한"),
    m3o=N(m3.loc["S_o", "coef"] * 100, ".1f", "outputs/03_회귀표.csv:M3 S_o", "M3 β_o"),
    m3p=N(m3.loc["S_o", "p"], ".2f", "outputs/03_회귀표.csv:M3 S_o p", "M3 p"),
    did=N(stk["did_car_share"]["coef"] * 100, ".1f", "outputs/03_파업.json:did_car_share.coef", "파업 DiD(%p)"),
    didlo=N(stk["did_car_share"]["lo"] * 100, ".1f", "outputs/03_파업.json:did_car_share.lo", "DiD 하한"),
    didhi=N(stk["did_car_share"]["hi"] * 100, ".1f", "outputs/03_파업.json:did_car_share.hi", "DiD 상한"),
    didday=N(sday.coef * 100, ".1f", "outputs/03_파업_시간대별.csv:주간 car_share", "주간 DiD(%p)"),
    didoff=N(soff.coef * 100, ".1f", "outputs/03_파업_시간대별.csv:09–16 car_share", "낮 비첨두 DiD(%p)"),
    didtrip=N(-(np.exp(sdayt.coef) - 1) * 100, ".0f", "outputs/03_파업_시간대별.csv:주간 log_trips → exp−1", "주간 통행 변화(%)"),
    busrun=N(-stk["bus_runs_seoul_stops_change"] * 100, ".0f", "outputs/03_파업.json:bus_runs_seoul_stops_change", "파업일 운행 변화(%)"),
    busmode=N(stk["stage1_change"]["일반버스"] * 100, ".1f", "outputs/03_파업.json:stage1_change.일반버스", "파업일 버스 통행 변화(%)"),
    ci=N(eqb["ci"], ".3f", "outputs/03_집중지수_부트.json:ci", "집중지수"),
    cilo=N(eqb["lo"], ".3f", "outputs/03_집중지수_부트.json:lo", "집중지수 하한"),
    cihi=N(eqb["hi"], ".3f", "outputs/03_집중지수_부트.json:hi", "집중지수 상한"),
    rat=N(eqb["ratio"], ".1f", "outputs/03_집중지수_부트.json:ratio", "1인당 노출비"),
    ratlo=N(eqb["ratio_lo"], ".1f", "outputs/03_집중지수_부트.json:ratio_lo", "노출비 하한"),
    rathi=N(eqb["ratio_hi"], ".1f", "outputs/03_집중지수_부트.json:ratio_hi", "노출비 상한"),
    typ_t=N(eqb["good_blind_types"].get("시간형", 0), "d", "outputs/03_집중지수_부트.json:good_blind_types.시간형", "시간형 동"),
    typ_a=N(eqb["good_blind_types"].get("상시형", 0), "d", "outputs/03_집중지수_부트.json:good_blind_types.상시형", "상시형 동"),
    nblind=N(s3["n_blind_cells"], ",d", "outputs/03_요약.json:n_blind_cells", "사각지대 셀"),
    sens_lo=N(sens[sens.space_t == 50].share_good_blind_among_good.min() * 100, ".0f", "outputs/03_민감도.csv:min", "민감도 하한(%)"),
    sens_hi=N(sens[sens.space_t == 50].share_good_blind_among_good.max() * 100, ".0f", "outputs/03_민감도.csv:max", "민감도 상한(%)"),
    vkm=N(c4["extra_vehicle_km_base"] / 1e8, ".1f", "outputs/04_탄소.json:extra_vehicle_km_base", "추가 차량km(억)"),
    kmpass=N(c4["bus_km_per_dong_pass"], ".2f", "outputs/04_탄소.json:bus_km_per_dong_pass", "동 통과당 버스km"),
    gb_trips=N(s3["good_blind_trips_share_of_blind"] * 100, ".0f", "outputs/03_요약.json:good_blind_trips_share_of_blind", "사각 셀 출발통행 중 공간양호 몫(%)"),
    # 시간대별 계수(03i B4)
    bn=N(-b4.loc["So_night", "Estimate"] * 100, ".1f", "outputs/03_회귀표_시간대분리.csv:B4 So_night", "심야 −β_o(%p)"),
    bnlo=N(-b4.loc["So_night", "97.5%"] * 100, ".1f", "outputs/03_회귀표_시간대분리.csv:B4 So_night 97.5%", "심야 −β_o 하한"),
    bnhi=N(-b4.loc["So_night", "2.5%"] * 100, ".1f", "outputs/03_회귀표_시간대분리.csv:B4 So_night 2.5%", "심야 −β_o 상한"),
    bn25=N(-b4.loc["So_night", "Estimate"] * 100 * 0.25, ".1f", "outputs/03_회귀표_시간대분리.csv:B4 So_night × 0.25", "심야 log0.25당(%p)"),
    bdw=N(-b4.loc["Sd_dawn", "Estimate"] * 100, ".1f", "outputs/03_회귀표_시간대분리.csv:B4 Sd_dawn", "새벽 −β_d(%p)"),
    bdyo=N(b4.loc["So_day", "Estimate"] * 100, "+.1f", "outputs/03_회귀표_시간대분리.csv:B4 So_day", "주간 β_o(%p)"),
    bdyop=N(b4.loc["So_day", "Pr(>|t|)"], ".2f", "outputs/03_회귀표_시간대분리.csv:B4 So_day p", "주간 β_o p"),
    bdyd=N(b4.loc["Sd_day", "Estimate"] * 100, "+.1f", "outputs/03_회귀표_시간대분리.csv:B4 Sd_day", "주간 β_d(%p)"),
    m5o=N(-reg[reg.model.str.startswith("M5")].set_index("var").loc["S_o", "coef"] * 100, ".1f", "outputs/03_회귀표.csv:M5 S_o", "평일만 −β_o(%p)"),
    m5p=N(reg[reg.model.str.startswith("M5")].set_index("var").loc["S_o", "p"], ".3f", "outputs/03_회귀표.csv:M5 S_o p", "평일만 p"),
    # 시간대별 탄소(04c)
    nd=N(nd["기본"]["t"], ",.0f", "outputs/04c_시간대별_탄소.json:band_nd.기본.t", "심야·새벽 연관 배출(t)"),
    ndlo=N(nd["기본"]["ci_lo"], ",.0f", "outputs/04c_시간대별_탄소.json:band_nd.기본.ci_lo", "심야·새벽 95% 하한(t)"),
    ndhi=N(nd["기본"]["ci_hi"], ",.0f", "outputs/04c_시간대별_탄소.json:band_nd.기본.ci_hi", "심야·새벽 95% 상한(t)"),
    ndmin=N(nd["보수"]["ci_lo"], ",.0f", "outputs/04c_시간대별_탄소.json:band_nd.보수.ci_lo", "심야·새벽 시나리오 하한(t)"),
    ndmax=N(nd["낙관"]["ci_hi"], ",.0f", "outputs/04c_시간대별_탄소.json:band_nd.낙관.ci_hi", "심야·새벽 시나리오 상한(t)"),
    ndpct=N(cb["nd_vs_common"] * 100, ".0f", "outputs/04c_시간대별_탄소.json:nd_vs_common", "심야·새벽 ÷ 공통계수 상한(%)"),
    ngt=N(cb["band_night"]["기본"]["t"], ",.0f", "outputs/04c_시간대별_탄소.json:band_night.기본.t", "심야 22–05 t(t)"),
    ngtlo=N(cb["band_night"]["기본"]["ci_lo"], ",.0f", "outputs/04c_시간대별_탄소.json:band_night.기본.ci_lo", "심야 22–05 ci_lo(t)"),
    ngthi=N(cb["band_night"]["기본"]["ci_hi"], ",.0f", "outputs/04c_시간대별_탄소.json:band_night.기본.ci_hi", "심야 22–05 ci_hi(t)"),
    dwn=N(cb["band_dawn"]["기본"]["t"], ",.0f", "outputs/04c_시간대별_탄소.json:band_dawn.기본.t", "새벽 05–07 t(t)"),
    dwnlo=N(cb["band_dawn"]["기본"]["ci_lo"], ",.0f", "outputs/04c_시간대별_탄소.json:band_dawn.기본.ci_lo", "새벽 05–07 ci_lo(t)"),
    dwnhi=N(cb["band_dawn"]["기본"]["ci_hi"], ",.0f", "outputs/04c_시간대별_탄소.json:band_dawn.기본.ci_hi", "새벽 05–07 ci_hi(t)"),
    day=N(cb["band_day"]["기본"]["t"], ",.0f", "outputs/04c_시간대별_탄소.json:band_day.기본.t", "주간 추정값 그대로(t, 합산 안 함)"),
    daylo=N(cb["band_day"]["기본"]["ci_lo"], ",.0f", "outputs/04c_시간대별_탄소.json:band_day.기본.ci_lo", "주간 95% 하한"),
    dayhi=N(cb["band_day"]["기본"]["ci_hi"], ",.0f", "outputs/04c_시간대별_탄소.json:band_day.기본.ci_hi", "주간 95% 상한"),
    # 파업: 차량 통행 수
    didp10=N(stk["did_car_share"]["coef"] * 10, ".2f", "outputs/03_파업.json:did_car_share.coef ÷ 10", "버스비중 10%p당 차량비중(%p)"),
    dcar=N((np.exp(stc.loc["주간 07–22", "coef"]) - 1) * 100, "+.1f", "outputs/03_파업_차량통행.csv:주간 exp(coef)−1", "주간 차량통행 DiD(%)"),
    dcarlo=N((np.exp(stc.loc["주간 07–22", "lo"]) - 1) * 100, "+.1f", "outputs/03_파업_차량통행.csv:주간 lo", "주간 차량통행 하한(%)"),
    dcarhi=N((np.exp(stc.loc["주간 07–22", "hi"]) - 1) * 100, "+.1f", "outputs/03_파업_차량통행.csv:주간 hi", "주간 차량통행 상한(%)"),
    dcaroff=N((np.exp(stc.loc["평일 낮 비첨두 09–16", "coef"]) - 1) * 100, "+.1f", "outputs/03_파업_차량통행.csv:09–16 exp(coef)−1", "09–16 차량통행 DiD(%)"),
    carall=N(stk["stage1_change"]["차량"] * 100, ".1f", "outputs/03_파업.json:stage1_change.차량", "파업일 차량 통행 변화(%)"),
    # CNG 민감도(04c)
    avoided_b=N(cb["band_avoided_t_blind"] / 1e4, ".2f", "outputs/04c_시간대별_탄소.json:band_avoided_t_blind", "시간대별 계수 회피 배출(만 t)"),
    cng3c=N(cng_pos("common", 3.0, "낙관 1.2"), "d", "outputs/04c_CNG_민감도.csv:common×3×1.2", "공통계수 3배·재차1.2 순감축 셀"),
    cng3b=N(cng_pos("band", 3.0, "낙관 1.2"), "d", "outputs/04c_CNG_민감도.csv:band×3×1.2", "시간대계수 3배·재차1.2 순감축 셀"),
    g3=N(float(cng.loc[cng.car_mult == 3.0, "car_g_km"].iloc[0]), ".0f", "outputs/04c_CNG_민감도.csv:car_g_km(3배)", "3배 승용차 계수 g/km"),
    kmpl3=N(cb["kmpl_at_3x"], ".1f", "outputs/04c_시간대별_탄소.json:kmpl_at_3x", "3배 계수의 휘발유 연비 환산(km/L)"),
    bemed=N(cb["cng_be_mult_common"]["median_finite"], ".0f", "outputs/04c_시간대별_탄소.json:cng_be_mult_common.median_finite", "셀별 손익분기 승용차 계수 배수 중앙(공통 계수)"),
    cng2b=N(cng_pos("band", 2.0, "낙관 1.2"), "d", "outputs/04c_CNG_민감도.csv:band×2×1.2", "시간대계수 2배·재차1.2 순감축 셀"),
    drtb=N(cb["band_drt_pos"], "d", "outputs/04c_시간대별_탄소.json:band_drt_pos", "DRT 양(+) 셀(시간대 계수)"),
    beb=N(cb["band_ebus_be_med_nd"], ".2f", "outputs/04c_시간대별_탄소.json:band_ebus_be_med_nd", "심야·새벽 셀 전기버스 손익분기 전력소비 중앙(kWh/km)"),
    # 재배분(시간대별 계수, 첨두 제외)
    p2sg=N(r5["topN_space_good"] * 100, ".0f", "outputs/05_재배분_시간대_첨두제외.json:topN_space_good", "상위20 공간양호 비율(%)"),
    p2runs=N(r5["topN_moved_runs_yr"] / 1e4, ".1f", "outputs/05_재배분_시간대_첨두제외.json:topN_moved_runs_yr", "상위20 이동 운행(만 회/년)"),
    p2dawn=N(r5["topN_tbins"].get("wk|05-07", 0), "d", "outputs/05_재배분_시간대_첨두제외.json:topN_tbins.wk|05-07", "상위20 중 평일 05–07"),
)
EQ_SIG = ", 구간이 1을 포함해 유의하지 않음" if eqb["ratio_lo"] <= 1 <= eqb["ratio_hi"] else ""
PANEL_N = N(int(m1.loc["S_o", "n"]), ",d", "outputs/03_회귀표.csv:n", "패널 행 수")

# ---------------- 문서 서식 ----------------
FONT = "맑은 고딕"
HDR = 2.4; BODY = 17.0 - HDR
doc = Document()
sec = doc.sections[0]
sec.page_height, sec.page_width = Cm(29.7), Cm(21.0)
for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
    setattr(sec, side, Cm(2.0))
st = doc.styles["Normal"]; st.font.name = FONT; st.font.size = Pt(10)
st.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
st.paragraph_format.space_after = Pt(1); st.paragraph_format.space_before = Pt(0); st.paragraph_format.line_spacing = 1.08
def shade(cell, hexcolor):
    tcPr = cell._tc.get_or_add_tcPr(); sh = OxmlElement("w:shd")
    sh.set(qn("w:val"), "clear"); sh.set(qn("w:color"), "auto"); sh.set(qn("w:fill"), hexcolor); tcPr.append(sh)
def runs(p, text, size=None, color=None):
    """**굵게** 표기 지원"""
    for i, part in enumerate(re.split(r"\*\*", text)):
        if not part: continue
        r = p.add_run(part); r.bold = (i % 2 == 1)
        r.font.name = FONT; r._element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
        if size: r.font.size = Pt(size)
        if color: r.font.color.rgb = RGBColor.from_string(color)
    return p
def para(cell_or_doc, text, size=10, bold=False, align=None, before=0, after=1, color=None, bullet=False):
    p = cell_or_doc.add_paragraph()
    if bullet: text = "· " + text
    runs(p, f"**{text}**" if bold else text, size, color)
    p.paragraph_format.space_before = Pt(before); p.paragraph_format.space_after = Pt(after)
    if align: p.alignment = align
    return p
def fig(cell, path, width_cm, caption):
    p = cell.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(str(path), width=Cm(width_cm))
    p.paragraph_format.space_after = Pt(0)
    para(cell, caption, size=8, color="444444", after=3)
def set_col_widths(table, widths):
    for row in table.rows:
        for i, w in enumerate(widths):
            row.cells[i].width = Cm(w)
def borders(table):
    tbl = table._tbl; tblPr = tbl.tblPr
    b = OxmlElement("w:tblBorders")
    for e in ("top", "left", "bottom", "right", "insideH", "insideV"):
        x = OxmlElement(f"w:{e}"); x.set(qn("w:val"), "single"); x.set(qn("w:sz"), "4"); x.set(qn("w:color"), "808080"); b.append(x)
    tblPr.append(b)
def small_table(cell, rows, widths, header_fill="EDEDED", size=8):
    k = min(1.0, (BODY - 0.5) / sum(widths)); widths = [w * k for w in widths]  # 셀 안쪽 여백만큼 줄여 넘침 방지
    t = cell.add_table(rows=len(rows), cols=len(rows[0])); borders(t)
    for i, row in enumerate(rows):
        for j, v in enumerate(row):
            c = t.cell(i, j); c.text = ""
            p = c.paragraphs[0]; runs(p, str(v), size); p.paragraph_format.space_after = Pt(0)
            if i == 0: shade(c, header_fill); p.runs and setattr(p.runs[0], "bold", True)
    t.autofit = False
    tblPr = t._tbl.tblPr
    for e in tblPr.findall(qn("w:tblW")) + tblPr.findall(qn("w:tblLayout")): tblPr.remove(e)
    tw_ = OxmlElement("w:tblW"); tw_.set(qn("w:w"), str(int(sum(widths) * 567))); tw_.set(qn("w:type"), "dxa")
    lay = OxmlElement("w:tblLayout"); lay.set(qn("w:type"), "fixed")
    style_el = tblPr.find(qn("w:tblStyle"))
    idx = 1 if style_el is not None else 0
    tblPr.insert(idx, tw_); tblPr.insert(idx + 1, lay)
    grid = t._tbl.tblGrid
    for gc, w in zip(grid.findall(qn("w:gridCol")), widths): gc.set(qn("w:w"), str(int(w * 567)))
    set_col_widths(t, widths)
    nxt = t._tbl.getnext()  # python-docx가 표 뒤에 넣는 빈 문단을 작게
    if nxt is not None and nxt.tag == qn("w:p"):
        from docx.text.paragraph import Paragraph
        pp = Paragraph(nxt, cell); pp.paragraph_format.space_after = Pt(2); pp.paragraph_format.line_spacing = Pt(4)
    return t

# ---------------- 표지 ----------------
para(doc, "- AI와 함께하는 교통문제 해결을 위한 데이터 분석 공모전 -", 12, align=WD_ALIGN_PARAGRAPH.CENTER, before=150)
para(doc, "분석보고서", 22, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, before=6, after=24)
para(doc, "같은 동네, 다른 시간", 18, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
para(doc, "지도에 없는 '시간 사각지대'가 만드는 차량 이동과 탄소", 14, align=WD_ALIGN_PARAGRAPH.CENTER, after=40)
para(doc, NAME, 13, align=WD_ALIGN_PARAGRAPH.CENTER)
para(doc, "2026년 10월", 11, align=WD_ALIGN_PARAGRAPH.CENTER, after=30)
para(doc, f"분석 코드: {GITHUB}", 10, align=WD_ALIGN_PARAGRAPH.CENTER, color="444444")
doc.add_page_break()

# ---------------- 양식 표 ----------------
T = doc.add_table(rows=0, cols=2); borders(T); T.alignment = WD_TABLE_ALIGNMENT.CENTER
def row(label):
    r = T.add_row(); a, b = r.cells
    a.width, b.width = Cm(HDR), Cm(BODY); shade(a, "F2F2F2")
    a.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    a.text = ""; p = a.paragraphs[0]; runs(p, label, 10); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    b.text = ""; return b
def first(cell, text, **kw):
    p = cell.paragraphs[0]; runs(p, text, kw.get("size", 10)); p.paragraph_format.space_after = Pt(kw.get("after", 1)); return p

# 1. 이름/팀명
c = row("이름/팀명"); first(c, NAME)
# 2. 주제
c = row("주제"); first(c, f"**{TITLE}**")
para(c, "서울 생활이동(출도착 행정동×수단) 데이터로 본 대중교통 '공간-시간 불일치'와 차량 배출, 그리고 운행 재배분 처방", 9, color="444444")

# 3. 분석 배경 및 목적 (1쪽: 결론 우선)
c = row("분석 배경\n및 목적")
first(c, "**핵심 결과 (헤드라인)**", size=10)
small_table(c, [
    ["① 공간 기준으로는 보이지 않는 사각지대", "② 심야·새벽 시간 사각지대와 연관된 차량 배출", "③ 운행 총량 그대로 낮→새벽 재배분(시뮬레이션)"],
    [f"**{X['good_blind']}개 동**\n서울시 800m 기준 '양호' {X['n_good']}개 동 중 {X['share_gb']}%가 특정 시간대엔 공급이 그 시간대 서울 동 하위 20%",
     f"**연 {X['nd']} tCO₂ (22–07시)**\n시간대별 계수로 본 연관 추정, 95% 구간 {X['ndlo']}~{X['ndhi']} t. 낮 시간은 평상시·파업 자료 모두 근거가 약해 제외",
     f"**상위 20셀 연 {X['p2top']} tCO₂ 순감축**\n({X['p2toplo']}~{X['p2tophi']} t, 1회당 {X['kgrun']} kg) 운행·버스km 불변, 기증 셀 손실 차감, 첨두 운행 유지. 단순 CNG 증회는 {X['cells']}개 셀 전부 순증가(승용차 계수 3배에서도 순감축 {X['cng3b']}개 이하)"],
], [5.0, 5.0, 4.6], header_fill="FBE3D2", size=8.5)
para(c, "**현황.** 서울시는 2026년 8월 21일, 지하철역이나 중앙·가로변 버스전용차로에서 800m 이내인지를 따지는 '빠른 대중교통 접근성(ART)' 지표로 서울 전역 대중교통 사각지대를 전수조사하고, 2030년까지 자율주행버스를 500대 규모로 늘리며 심야·새벽 자율주행버스를 운영하겠다고 발표했다(서울신문, 2026-08-21).", 9.5)
para(c, "**문제.** 800m 기준은 '어디에' 정류장이 있는지만 본다. 같은 동네라도 낮 비첨두·주말·심야처럼 '언제' 버스가 줄어드는지는 지도에 나타나지 않는다. 이 시간 사각지대에서 같은 출발·도착지의 같은 거리 이동이 차로 더 이뤄진다면, 공간 기준 정책은 그 차량 이동과 탄소를 놓친다.", 9.5)
para(c, "**목적.** (RQ1) 공간 기준으로 양호한 동 중 시간대별로 공급이 크게 약해지는 '시간 사각지대'는 어디·언제 있고, 같은 OD의 차량 비중과 어떤 관계인가 (RQ2) 그 부담은 고령 비율이 높은 동에 몰리는가 (RQ3) 연관된 추가 차량 배출은 연간 얼마인가 (RQ4) 어디에·언제·어떤 수단으로 보강해야 순감축인가. 모든 핵심 결과를 '시간 축' 비교로 제시해, 공간 단면 분석과 다른 근거를 서울시 ART 조사에 더하는 것이 참여 동기다.", 9.5)
fig(c, FIG / "그림1_공간시간_2x2지도.png", 14.2, "그림 1. 공간(800m)×시간 2×2 분류. 진한 주황 = 공간 양호인데 특정 시간대 공급이 같은 시간대 서울 동 순위 하위 20%인 동(상대 개념).")

# 4. 활용 데이터
c = row("활용\n데이터")
first(c, "공공데이터 중심, 2026년 9월 화~목 6일(9/8·9·10·15·16·17)과 토·일 4일(9/12·13·19·20) 분석(추석 주간 제외). 개인정보 없는 행정동·시간 집계 자료만 사용.", size=9)
small_table(c, [
    ["활용 데이터(명)", "제공기관", "플랫폼", "URL"],
    ["수도권 생활이동(출도착 행정동별 수단) OA-22657 — 수요·수단(주 데이터)", "서울특별시·KT", "서울 열린데이터광장", "data.seoul.go.kr/dataList/OA-22657/F/1/datasetView.do"],
    ["서울시 노선별 정류장별 총 버스 운행횟수 OA-21220 — 시간대별 버스 공급", "서울특별시", "서울 열린데이터광장", "data.seoul.go.kr/dataList/OA-21220/F/1/datasetView.do"],
    ["서울시 버스정류소 위치정보 OA-15067 — 정류소 좌표·중앙/가로변 차로", "서울특별시", "서울 열린데이터광장", "data.seoul.go.kr/dataList/OA-15067/S/1/datasetView.do"],
    ["서울교통공사 열차운행현황 OA-13318 — 지하철 시격", "서울교통공사", "서울 열린데이터광장", "data.seoul.go.kr/dataList/OA-13318/F/1/datasetView.do"],
    ["행정동 단위 서울 생활인구(내국인) OA-14991 — 공백 노출", "서울특별시·KT", "서울 열린데이터광장", "data.seoul.go.kr/dataList/OA-14991/S/1/datasetView.do"],
    ["지역별(행정동) 성별 연령별 주민등록 인구수 — 65세 이상 비율", "행정안전부", "공공데이터포털", "data.go.kr/data/15097972/fileData.do"],
    ["행정동 경계(ver20260701) / 지하철역 위치", "vuski / OpenStreetMap", "GitHub / Overpass API", "github.com/vuski/admdongkor / openstreetmap.org"],
], [6.3, 2.2, 2.4, 3.7], size=7.5)
para(c, "생활인구는 2026년 9월분이 아직 공개되지 않아(최신 2026-07) 계절이 같은 2025년 9월분을 썼다. 선정 이유: 생활이동 OD×수단은 같은 출발·도착지의 시간대별 수단 선택을 담은 유일한 공개 자료이고, 버스 운행횟수는 일자·시간(1시간) 해상도로 공급을 잰다. 승하차 인원은 수요와 섞여 공급 지표로 쓰지 않았다. 배출계수는 원문을 확인한 공식 자료만 썼다(참고문헌).", 8.5)

# 5. 분석과정 및 방법
c = row("분석과정\n및 방법")
first(c, f"**① 수집·전처리.** 일별 zip(일 약 800만 행)을 하나씩 풀어 duckdb로 서울 내부(출발·도착 모두 서울) 통행만 (출발 동, 도착 동, 출발 시, 수단)으로 집계한 뒤 임시 파일을 지웠다. 차량 비중 = 차량 ÷ (차량+일반버스+광역버스+지하철). 500m 미만 차량 행(위치 오차)·동 내부 통행 제외, 일평균 20통행 이상 OD쌍만 남겨 **{PANEL_N}행 패널**(OD×8개 시간 구간×평일/주말, 통행의 92% 포괄)을 만들었다.", size=9)
para(c, "**② 공급 지표 S.** 동 안 정류소의 운행횟수를 (노선, 시)마다 최댓값으로 잡아 같은 버스의 중복을 없앤 뒤 합산하고, 지하철은 역 800m 안에 드는 동 면적 비율 × 시간당 열차 수(서울교통공사 시격)로 더해 S = log(1 + 버스 + 3×열차). 공간 양호 = 동 면적의 50% 이상이 지하철역·중앙/가로변 버스전용차로 정류소 800m 안(서울시 ART 근사).", 9)
para(c, f"**③ 같은 길, 다른 시간 모형.** 차량비중 ~ S_출발 + S_도착 | OD쌍 고정효과 + 시간구간×요일 고정효과(통행 가중, 출발 동 군집 표준오차). OD쌍 고정효과가 거리·동네 특성을 지우고, 같은 OD가 시간대에 따라 공급이 상대적으로 낮을 때 차가 더 쓰이는지(연관)만 본다. 계수는 심야(22–05)·새벽(05–07)·주간(07–22)마다 **그 시간대 안의 변동만으로 따로** 추정했다(OD×시간대 고정효과). 출발 동을 묶어 다시 뽑는 블록 부트스트랩 200회로 구간을 냈다.", 9)
para(c, "**④ 시간 사각지대 셀**(동×구간×요일, 상대 개념): 그 시간대·요일 서울 동 공급 순위 하위 20% ∧ p75(같은 시간대 상위 25% 동 수준)와의 공급 격차 상위 20% ∧ 출발 통행 50/일 이상. (x,y)∈{10,20,30}², 공간 기준 30/50/70% 민감도. **⑤ 탄소**: 공급을 p75로 올리는 반사실(관측 범위 안)의 차량 통행 감소 × 직선거리 × 우회계수 ÷ 재차인원 × g/km, 그 시간대 계수만 적용, 2026년 달력(평일 245·주말공휴일 120일). **⑥ 외생 충격**: 2026-01-13·14 시내버스 파업일 vs 같은 요일 대조일 이중차분. **⑦ 처방 시뮬레이션**: 증회(CNG)·DRT·전기버스 손익분기·같은 구 안 운행 재배분(총 운행·버스km 불변).", 9)

# 6. AI 기술 활용
c = row("AI 기술\n활용")
first(c, "**분석 기법(통계·ML).** 고차원 고정효과 가중회귀(pyfixest), 블록 부트스트랩, 이중차분, 한계효과 기반 탐욕 재배분 최적화. **생성형 AI(작업 보조).** Anthropic Claude Code(Claude Opus 5.5)를 코드 작성·실행, 데이터 구조 점검, 공식 출처 검색·원문 대조, 그림·보고서 초안에 사용. 사람은 주제 확정, 데이터 다운로드 일부, 검토·서명·제출을 맡았다. 주요 프롬프트: \"확정 주제의 분석·보고서·프로토타입을 완성하라. 데이터에서 확인하지 않은 수치·출처를 만들지 말고, 가정은 가정으로 표시하고, 상관을 인과로 쓰지 마라.\" 검증: 보고서의 모든 숫자는 코드가 결과 파일에서 읽어 넣었고 수치대조표(저장소 outputs/10_수치대조표.csv)로 추적된다.", size=9)

# 7. 분석 내용 및 결과
c = row("분석 내용\n및 결과")
first(c, "**(1) 같은 길, 다른 시간: 공급과 차량의 관계는 심야·새벽에서만 뚜렷하다**", size=10)
para(c, f"같은 출발·도착 동의 같은 거리 이동에서, 시간대를 모두 섞은 공통 계수로는 출발지 공급이 log 1단위(약 63%) 낮을 때 차량 비중이 {X['bo']}%p 높았다(95% {X['bolo']}~{X['bohi']}%p, 연관). 그러나 이 값은 주로 심야와 주간의 수준 차이에서 나온다. 평일만 쓰면 p={X['m5p']}로 경계선이다. 그래서 **시간대마다 그 시간대 안의 변동만으로 계수를 따로 구했다.** 심야(22–05시)는 출발지 공급 계수 **−{X['bn']}%p**(95% −{X['bnhi']}~−{X['bnlo']}; 공급이 log 0.25(약 22%) 낮으면 차량 비중 +{X['bn25']}%p), 새벽(05–07시)은 도착지 공급 계수 −{X['bdw']}%p로 뚜렷하다. 주간(07–22시)은 출발지 {X['bdyo']}%p(p={X['bdyop']}), 도착지 {X['bdyd']}%p로 관계가 없거나 반대 부호다. **파업으로 낮 시간 주장을 다시 점검했다.** 버스 파업일(서울 정류장 운행 {X['busrun']}% 감소)에 버스 의존 동일수록 차량 '비중'은 올랐다(버스 비중 10%p당 +{X['didp10']}%p, 낮 07–22시 기준 버스 비중 1단위당 +{X['didday']}%p). 하지만 차량 '통행 수'는 늘지 않았다(낮 {X['dcar']}%, 95% {X['dcarlo']}~{X['dcarhi']}%; 평일 09–16시 {X['dcaroff']}%; 서울 전체 차량 통행 {X['carall']}%). 비중이 오른 것은 대중교통 통행이 줄었기 때문이다(낮 통행 −{X['didtrip']}%). → 낮에 버스가 줄면 사람들은 차로 옮기기보다 이동을 줄인다. 낮 시간 추가 배출은 근거가 약해 헤드라인에서 뺐고, 낮 시간 공백은 탄소가 아니라 이동 기회의 문제로 다룬다.", 9)
fig(c, FIG / "그림2_같은OD_다른시간.png", 11.2, "그림 2. 같은 OD 안의 시간 변동(왼쪽: OD·시간대×요일 고정효과를 뺀 잔차, 20분위)과 모형별 출발지 계수(오른쪽, 파랑 = 시간대 안 변동만 쓴 계수).")
fig(c, FIG / "그림3_파업_이중차분.png", 10.5, "그림 3. 2026-01 시내버스 파업(외생 충격 하의 반응). 지하철 증회·무료 셔틀 등 동시 조치가 있어 인과 효과로 단정하지 않는다.")
para(c, f"**(2) 공간-시간 불일치: 서울시 기준 사각지대가 아닌데, 특정 시간엔 사각지대.** 800m 기준 양호 {X['n_good']}개 동 중 **{X['good_blind']}개 동({X['share_gb']}%)**에 시간 사각지대 셀이 있고(민감도 {X['sens_lo']}~{X['sens_hi']}%), 사각지대 셀 출발 통행의 **{X['gb_trips']}%**가 이 동들에서 나온다(그림 1). 그중 {X['typ_t']}개 동은 일부 시간대에만 낮은 '시간형', {X['typ_a']}개 동은 하루 대부분 낮은 '종일 저빈도형'이다. 시간 사각지대는 그 시간대 서울 동 순위로 정한 상대 개념이다. → 공간 기준 전수조사만으로는 이 동들이 조사에서 빠진다.", 9)
para(c, f"**(3) 탄소: 연관 배출은 심야·새벽에서 식별된다.** 공급을 p75로 올리는 반사실에 시간대별 계수를 적용하면, 연관 추가 배출은 심야·새벽(22–07시) **연 {X['nd']} tCO₂**다(95% {X['ndlo']}~{X['ndhi']} t, 재차·우회 시나리오 포함 {X['ndmin']}~{X['ndmax']} t). 나누면 심야 {X['ngt']} t(95% {X['ngtlo']}~{X['ngthi']})는 뚜렷하지만, 새벽 {X['dwn']} t({X['dwnlo']}~{X['dwnhi']})는 구간이 0을 포함한다. 주간 계수를 그대로 넣으면 주간 값은 {X['day']} t(95% {X['daylo']}~{X['dayhi']})로 음(−)이 된다. 공급이 늘면 차가 는다는 뜻이라 이론과 반대 부호이므로, 연관 근거로 쓰지 않고 합산하지 않았다. 시간대 공통 계수를 가정하면 {X['h1']}만 t({X['nonnight']}%가 심야 밖)지만, 이는 낮 시간 계수가 밤과 같다고 놓은 **상한 시나리오**다. 심야·새벽 값은 그 {X['ndpct']}%에 해당한다(그림 4). → 탄소 근거가 있는 곳은 새벽·심야이며, 서울시 새벽·심야 자율주행버스 계획의 시간대와 겹친다.", 9)
fig(c, FIG / "그림4_구간별_추가배출.png", 11.2, "그림 4. 시간 구간별 연관 추가 배출. 막대 = 시간대별 계수(오차막대: 부트스트랩 95%), 점선 = 시간대 공통 계수 가정(상한 시나리오).")
para(c, f"**(4) 부담은 고령 비율이 높은 동으로 기운다.** 시간 사각지대 셀의 생활인구(인원×시간)를 65세 이상 비율 순으로 쌓으면 집중지수 **{X['ci']}**(95% {X['cilo']}~{X['cihi']})로 고령 비율이 높은 동 쪽에 몰린다. 65세 이상 비율 상위 20% 동의 주민 1인당 노출은 하위 20% 동의 {X['rat']}배({X['ratlo']}~{X['rathi']}배{EQ_SIG})다(그림 5, 생태학적 지표). → 보강 우선순위에 고령 비율을 함께 써야 한다.", 9)
fig(c, FIG / "그림5_공백노출_집중곡선.png", 10.5, "그림 5. 65세 이상 비율 순 공백 노출 집중곡선. 행정동 단위 지표로 개인의 연령·취약성을 뜻하지 않는다.")
para(c, f"**(5) 어디에, 언제, 무엇을: 증회는 탄소로 정당화되지 않는다.** 사각지대 {X['cells']}개 셀을 p75까지 CNG 버스로 증회하면 회피 배출(공통 계수 {X['avoided']}만 t, 시간대별 계수 {X['avoided_b']}만 t)보다 버스 배출 {X['busem']}만 t가 커서 **{X['cngneg']}개 셀 전부 순배출이 늘어난다**. 승용차 계수를 낮게 잡은 탓인지 점검했다. 계수를 3배({X['g3']} g/km, 휘발유 연비 {X['kmpl3']} km/L 수준)로 올리고 재차인원을 1.2로 낮춰도 순감축 셀은 공통 계수 {X['cng3c']}개, 시간대별 계수 {X['cng3b']}개다. 2배·재차 1.2에서는 시간대별 계수 기준 {X['cng2b']}개다. 셀이 순감축이 되는 데 필요한 승용차 계수 배수는 셀 중앙값으로 {X['bemed']}배다(04c_CNG_민감도.csv). 승합 DRT(가정: 신차 평균 125.2 g/km)는 {X['drtb']}개 셀에서 순감축이다. 전기버스는 전력 소비가 {X['beb']} kWh/km 이하여야 순감축이다(심야·새벽 셀 중앙값; 국내 실측 전력 소비 원문은 미확보). **운행 재배분(시뮬레이션):** 같은 자치구에서 공급이 p75를 넘는 낮 비첨두·저녁 동·시간대의 운행 일부(일 20% 이내, 첨두 07–09·16–19와 심야·새벽 운행은 빼지 않음)를 옮긴다. 기증 셀의 차량 증가분을 차감한 순값으로 계산했다. 버스km가 늘지 않아 {X['p2cells']}개 셀이 순감축({X['p2neg']}개 음수), 전체 연 {X['p2all']} t, 상위 20셀 **{X['p2top']} t**({X['p2toplo']}~{X['p2tophi']})다. 상위 20셀 중 {X['p2dawn']}개가 평일 새벽 05–07시, {X['p2sg']}%가 공간 양호 동이다. '운행 1회'는 버스 노선 1회가 동 하나를 지나는 것이며, 상위 20셀에서 연 {X['p2runs']}만 회를 옮기고 1회당 {X['kgrun']} kg 순감축이다. 이 값은 연관 계수를 쓴 시뮬레이션이며 실제 효과가 아니다.", 9)

# 8. 정책제안 및 기대효과
c = row("정책제안\n및\n기대효과")
first(c, "**세 가지 제안 — 지도에 시간 축을 더하고, 차량을 늘리지 않고 옮기고, 저수요 시간은 작게.**", size=10)
small_table(c, [
    ["", "P1. ART 조사에 시간 축(T-ART)", "P2. 운행 총량 그대로 재배분", "P3. 저수요 시간대는 소형·저배출로"],
    ["내용", "공간 양호 동도 시간대별 공급을 같은 시간대 동 순위로 표시", "같은 구 안 p75 초과 낮 비첨두·저녁 운행 일부를 새벽·심야 사각지대로(첨두·심야 운행은 유지)", "새벽·심야·주말 저수요 셀은 대형 CNG 증회 대신 DRT·새벽동행/심야 자율주행버스 후보로"],
    ["결정 주체", "서울시 교통실(ART 전수조사)", "서울시 버스정책 부서·운수사(연례 노선·배차 조정)", "서울시 교통실·자치구"],
    ["자원", "분석 비용(공개 데이터, 코드 공개)", "추가 차량·버스km 없음(새벽 근무 조정 필요)", "DRT 차량·운영(비용 근거 미확보)"],
    ["근거 숫자", f"양호 {X['n_good']}동 중 {X['good_blind']}동이 시간 사각지대", f"상위 20셀 연 {X['p2top']} t, 1회당 {X['kgrun']} kg(시뮬레이션)", f"CNG 증회 {X['cngneg']}셀 전부 순배출↑(계수 3배에도 유지), DRT {X['drtb']}셀 순감축"],
    ["KPI", "공간 양호·시간 사각지대 동 수", "이동 운행 1회당 순감축, 수혜 통행", "셀 순감축 부호 전환, 고령 상위 동 공백 노출"],
], [1.7, 4.2, 4.3, 4.4], size=7.5)
top = pd.read_csv(OUT / "05_재배분_시간대_첨두제외.csv", dtype={"dong": str}).head(5)
rows_ = [["우선순위(P2)", "동", "요일·구간", "공간 양호", "65+ 비율", "순감축 t/년(범위)"]]
for i, r_ in enumerate(top.itertuples(), 1):
    rows_.append([str(i), r_.adm_nm.replace("서울특별시 ", ""), ("평일 " if r_.daytype == "wk" else "주말 ") + r_.tbin,
                  "○" if r_.space_good else "×", N(r_.old_share * 100, ".1f", f"outputs/05_재배분_시간대_첨두제외.csv:row{i}.old_share", f"상위{i} 65+") + "%",
                  f"{N(r_.net_t, '.1f', f'outputs/05_재배분_시간대_첨두제외.csv:row{i}.net_t', f'상위{i} 순감축')} ({r_.net_t_lo:.1f}~{r_.net_t_hi:.1f})"])
small_table(c, rows_, [2.0, 3.6, 2.6, 1.6, 1.6, 3.2], size=7.5)
para(c, f"우선순위 상위 20셀의 {X['p2sg']}%는 공간 양호 동(ART 기준으로는 보이지 않는 곳)이고, 나머지는 공간 불량 동으로 ART 조사와 겹친다. P2는 두 유형 모두에 적용된다. 탄소 기준 순위에 고령 비율을 가중한 순위는 결선 과제로 남긴다.", 8.5)

# 9. 기대효과
c = row("기대효과")
first(c, f"**적용 사례 1 — 서울시 ART 전수조사(교통실).** 같은 공개 데이터로 월별 갱신하는 T-ART 표를 조사 보조 자료로 붙이면 공간 기준에서 빠지는 {X['good_blind']}개 동과 시간대가 조사 대상에 들어오고, 사각지대 셀 출발 통행의 {X['gb_trips']}%가 그 동들에 있다.", size=9)
para(c, f"**적용 사례 2 — 연례 노선·배차 조정(버스정책 부서·운수사).** 낮 비첨두 운행 일부를 새벽 첫차 시간대로 당기면(노선별 첫차 조기화·구간 배차) 차량·버스km를 늘리지 않고 연 {X['p2top']}~{X['p2all']} tCO₂ 순감축(시뮬레이션). KPI는 이동 운행 1회당 순감축({X['kgrun']} kg).", 9)
para(c, "**적용 사례 3 — 새벽동행·심야 자율주행버스와 DRT 배치(교통실·자치구).** 저수요 셀은 대형 증회 대신 소형·전기 수단 후보로 걸러, 증회로 배출이 늘어나는 셀을 피한다. 프로토타입 「서울 버스시계(T-ART)」가 이를 한 화면에 보여준다(분석결과 이미지).", 9)
para(c, "**한계.** ① 생활이동은 KT 통신 신호 기반 추정치(수단 포함)이며 30분 미만 체류는 별도 통행으로 집계되지 않는다. ② 목적 데이터는 수단과 교차되지 않아 차량 통행의 목적은 말하지 않는다. ③ 형평성 지표는 행정동 단위 생태학적 지표다. ④ 공급-차량 비중 관계는 연관이며 주간에는 확인되지 않는다. 새벽 계수는 05–07 한 구간이라 평일·주말 대비로만 식별된다. ⑤ 파업 분석에는 지하철 증회·무료 셔틀 등 동시 조치가 섞여 있다. 그 밖에 승용차 계수는 신차 공인값, 재차인원은 가정(1.2~1.6), 전기버스 국내 실측 전력 소비는 미확보, 생활인구 2개 동(항동·상일2동) 미매칭.", 8.5)

# 10. 분석도구 및 참고문헌
c = row("분석도구\n및\n참고문헌")
first(c, f"**코드 저장소: {GITHUB}**", size=9.5)
para(c, "분석도구: Python 3.12, duckdb, pandas, pyfixest, geopandas·shapely, matplotlib(koreanize-matplotlib), python-docx, Leaflet 1.9.4. 실행: run_all.py(번호순).", 8.5)
refs = [
    "서울신문(2026-08-21) 「오세훈, 2030년 서울에 자율주행버스 500대 투입…심야도 운영」. m.go.seoul.co.kr/news/2026/08/21/20260821500122",
    "서울 열린데이터광장, 수도권 생활이동 매뉴얼 및 수단별 레이아웃(이동수단 코드 1~9). data.seoul.go.kr/dataVisual/seoul/capitalRegionLivingMigration.do",
    "환경부(2022-11-16) 「재작년 판매된 자동차 온실가스 배출량, 기준보다 29% 많아」(10인승 이하 승용·승합 평균 125.2 g/km). korea.kr/news/policyNewsView.do?newsId=148908381",
    "IPCC(2006) 2006 IPCC Guidelines, Vol.2 Ch.3 Mobile Combustion, Table 3.2.1(CNG 56,100 kg/TJ).",
    "에너지법 시행규칙 [별표] 에너지열량 환산기준 <개정 2022.11.21.>(도시가스 LNG 순발열량 38.5 MJ/Nm³). law.go.kr",
    "서울특별시 교통 누리집(2013-06-17) 「서울시, 시내버스 연비효율 높여 업계 재정부담 줄인다」(CNG 실운행 연비 1.8 km/㎥). news.seoul.go.kr/traffic/archives/11516",
    "기후에너지환경부(2025-12-18) 보도자료 「전력배출계수 갱신 주기 3년에서 1년으로 단축」(2023년 0.4173 tCO₂eq/MWh). korea.kr/briefing/pressReleaseView.do?newsId=156735726",
    "Kim S., Kim T., Jeon J.(2025) Implementing dynamic distance-time conversion factors…, PLoS One, doi:10.1371/journal.pone.0330266 (서울 우회계수 1.215·1.296).",
    "경향신문(2026-01-13), 아주경제(2026-01-12), 헤럴드경제(2026-01-14): 서울 시내버스 파업 일정과 지하철 172회 증회·막차 연장·무료 셔틀 670여 대 투입.",
    "자료 라이선스: 서울 열린데이터광장·공공데이터포털 공공누리, OpenStreetMap ODbL, vuski/admdongkor(저장소 라이선스). 상세는 저장소 data/README.md.",
]
for i, rtxt in enumerate(refs, 1):
    para(c, f"[{i}] {rtxt}", 7.5)
para(c, "AI 활용 내역: 저장소 docs/AI활용내역.md(작업 단계별 사용 범위·사람 검토 항목).", 7.5)

# 11. 분석결과 이미지(필수)
c = row("분석결과\n이미지\n(필수)")
fig(c, FIG / "그림6_T-ART_프로토타입.png", 12.4, "그림 6. 시연 프로토타입 「서울 버스시계(T-ART)」 행정용 화면. 시간대를 고르면 동별 공급과 시간 사각지대가 지도에 표시되고, 동을 누르면 보강 수단별 순감축을 보여 준다(설치 없이 브라우저에서 실행).")

out_docx = REPORT / f"{FILE_STEM}.docx"
doc.save(out_docx)
pd.DataFrame(LEDGER).to_csv(OUT / "10_수치대조표.csv", index=False, encoding="utf-8-sig")
print("saved", out_docx, "numbers", len(LEDGER))
if "--pdf" in sys.argv:
    from docx2pdf import convert
    convert(str(out_docx), str(REPORT / f"{FILE_STEM}.pdf"))
    print("pdf saved")
