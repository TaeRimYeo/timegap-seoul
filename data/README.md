# 데이터 출처와 받는 방법

원자료는 저장소에 올리지 않는다(용량·재배포). 아래 파일을 같은 이름으로 두면 `python -I run_all.py`가 재현한다.

## data/raw/ (사람이 내려받음)
| 폴더/파일 | 데이터 | 제공 | 이용 조건 | 받는 곳 |
|---|---|---|---|---|
| 생활이동_OD/seoul_trans_admdong3_final_YYYYMMDD.zip (2026-09, 일별) | 수도권 생활이동(출도착 행정동별 수단) OA-22657 | 서울특별시·KT | 공공누리 제1유형(출처표시) | https://data.seoul.go.kr/dataList/OA-22657/F/1/datasetView.do |
| 버스운행/tpss_sta_route_hturn_2026.09.07-09.13.csv, 2026.09.14-09.20.csv | 서울시 노선별 정류장별 총 버스 운행횟수 OA-21220 | 서울특별시 | 공공누리 제1유형 | https://data.seoul.go.kr/dataList/OA-21220/F/1/datasetView.do |
| 버스정류소/서울시버스정류소위치정보(20260902).xlsx | 서울시 버스정류소 위치정보 OA-15067 | 서울특별시 | 공공누리 제1유형 | https://data.seoul.go.kr/dataList/OA-15067/S/1/datasetView.do |
| 지하철/서울교통공사_열차운행현황_20240331.csv | 서울교통공사 열차운행현황 OA-13318 | 서울교통공사 | 공공누리 제1유형 | https://data.seoul.go.kr/dataList/OA-13318/F/1/datasetView.do |
| 형평성/LOCAL_PEOPLE_DONG_202607.csv | 행정동 단위 서울 생활인구(내국인) OA-14991 (비교용) | 서울특별시·KT | 공공누리 제1유형 | https://data.seoul.go.kr/dataList/OA-14991/S/1/datasetView.do |

## data/external/ (에이전트가 공개 경로로 내려받음, 2026-10-16)
| 파일 | 데이터 | 이용 조건 | 받는 곳 |
|---|---|---|---|
| LOCAL_PEOPLE_DONG_202509.zip | 생활인구 2025-09(주 자료, 계절 일치) | 공공누리 제1유형 | OA-14991 파일 목록 |
| tpss_sta_route_hturn_202601.zip | 버스 운행횟수 2026-01(파업 분석) | 공공누리 제1유형 | OA-21220 파일 목록 |
| 생활이동_OD/seoul_trans_admdong3_final_202601{06,07,13,14,20,21}.zip | 생활이동 2026-01(파업 분석) | 공공누리 제1유형 | OA-22657 파일 목록 |
| MOIS_행정동_성연령별_주민등록인구_20260930.csv | 행정안전부 지역별(행정동) 성별 연령별 주민등록 인구수 | 이용허락범위 제한 없음 | https://www.data.go.kr/data/15097972/fileData.do |
| HangJeongDong_ver20260701.geojson, HangJeongDong_ver20200101.geojson | 행정동 경계 | 저장소 라이선스 표기 없음(출처 표기) | https://github.com/vuski/admdongkor |
| osm_stations_seoul.json | 서울 도시철도역 위치(`src/01a_osm_stations.py`) | ODbL, © OpenStreetMap contributors | Overpass API |
| 수도권생활이동_매뉴얼.pdf, 수도권생활이동_수단별_레이아웃.xlsx, 전국_행정동_코드정보.zip | 생활이동 매뉴얼·코드 | 공공누리 | https://data.seoul.go.kr/dataVisual/seoul/capitalRegionLivingMigration.do |
| 에너지법시행규칙_별표_열량환산기준.pdf, IPCC2006_V2_Ch3_Mobile.pdf | 배출계수 원문 | — | law.go.kr, ipcc-nggip.iges.or.jp |

## data/interim/ (코드가 만듦, 커밋하지 않음)
`od_YYYYMMDD.parquet`(서울 내부 OD×시×수단), `odx_*.parquet`(서울→외부), `02_패널.parquet`, `02_생활인구.parquet`, `03_파업패널.parquet`.

개인정보: 모든 자료가 행정동·시간 단위 집계값이며 개인 단위 자료는 쓰지 않았다.
