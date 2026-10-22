"""서울 도시철도역 좌표를 OpenStreetMap(Overpass API)에서 받는다 → data/external/osm_stations_seoul.json
(서울 열린데이터광장 OA-21232 '역사마스터'는 시트형이라 자동 다운로드가 어려워 대체. 라이선스: ODbL)"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).parent))
from common import *
import json, urllib.request, urllib.parse

Q = """[out:json][timeout:180];
area["name"="서울특별시"]["admin_level"="4"]->.a;
( node["railway"="station"](area.a); node["railway"="halt"](area.a); )->.st;
.st out tags center;
rel(bn.st)["type"="route"]["route"~"subway|train|light_rail|monorail"];
out tags;
( rel["type"="route"]["route"~"subway|light_rail"](area.a); )->.r;
.r out tags;
"""
import time
raw = None
for url in ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter",
            "https://maps.mail.ru/osm/tools/overpass/api/interpreter", "https://overpass.private.coffee/api/interpreter"]:
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, data=urllib.parse.urlencode({"data": Q}).encode(),
                                         headers={"User-Agent": "timegap-seoul research"})
            raw = urllib.request.urlopen(req, timeout=300).read(); print("ok", url); break
        except Exception as e:
            print("fail", url, e); time.sleep(5)
    if raw: break
(EXT / "osm_stations_seoul.json").write_bytes(raw)
d = json.loads(raw)["elements"]
print("elements", len(d), "nodes", sum(e["type"] == "node" for e in d))
