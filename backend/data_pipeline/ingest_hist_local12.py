"""민선 1~8회 기초단체장 후보 전원(낙선 포함, 정확 득표) -> candidates/results.

소스: info.nec.go.kr 역대선거 개표현황(VCCP09, electionId=0000000000, electionCode=4).
- 위키 기반 local_mayors(3~8회, 득표수 미수록)를 역대 개표결과로 '경합 시군구만' 교체
  (시군구별 부분 DELETE → 무투표 단체장은 local_mayors 당선자 유지).
- 1·2회는 local_mayors 미수록이라 역대 경합분만 적재(무투표는 소수, 누락 허용).
일반구 도시는 시 합계행+구별 분해행 구조 → 시군구별 '첫 유효행(시 합계)'만 채택.
선행: ingest.py → ingest_local.py → ingest_local_9.py 후 실행. 이후 precompute.py.
실행: python backend/data_pipeline/ingest_hist_local12.py
"""
import pathlib
import sqlite3
import sys
import time
import warnings

import httpx
import pandas as pd  # noqa: F401  (collect_nec9.parse_districts 가 사용)

warnings.filterwarnings("ignore")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from collect_nec9 import parse_districts  # noqa: E402
from ingest_council import build_region_list, match_sigungu  # noqa: E402
from ingest import resolve_party  # noqa: E402

DB = pathlib.Path(__file__).resolve().parent.parent / "db" / "election.sqlite"
BASE = "https://info.nec.go.kr"
OFFICE = "기초단체장"
HOE_ENAME = {1: "19950627", 2: "19980604", 3: "20020613", 4: "20060531",
             5: "20100602", 6: "20140604", 7: "20180613", 8: "20220601"}
STD2SHORT = {
    "11": "서울", "26": "부산", "27": "대구", "28": "인천", "29": "광주", "30": "대전",
    "31": "울산", "41": "경기", "42": "강원", "43": "충북", "44": "충남",
    "45": "전북", "46": "전남", "47": "경북", "48": "경남", "50": "제주",
}


def fetch(cli, ename, city):
    data = {
        "electionId": "0000000000", "requestURI": "/electioninfo/0000000000/vc/vccp09.jsp",
        "topMenuId": "VC", "secondMenuId": "VCCP09", "menuId": "VCCP09",
        "statementId": "VCCP09_#4", "oldElectionType": "0", "electionType": "4",
        "electionName": ename, "electionCode": "4", "cityCode": city,
        "sggCityCode": "0", "townCode": "-1", "sggTownCode": "0",
    }
    return cli.post(f"{BASE}/electioninfo/electionInfo_report.xhtml", data=data).text


def _is_num(s):
    try:
        float(s); return True
    except (ValueError, TypeError):
        return False


def main():
    cli = httpx.Client(timeout=60, verify=False, headers={"User-Agent": "Mozilla/5.0"}, follow_redirects=True)
    cli.get(f"{BASE}/main/showDocument.xhtml?electionId=0000000000&topMenuId=VC&secondMenuId=VCCP09")
    con = sqlite3.connect(DB)
    cur = con.cursor()
    rlist = build_region_list(con)

    for hoe, ename in HOE_ENAME.items():
        ncand = nwin = nmiss = nreg = 0
        miss = set()
        for city, short in STD2SHORT.items():
            ct, _ = parse_districts(fetch(cli, ename, city))
            seen = set()
            for r in ct:
                if r["sigungu"] in seen:
                    continue  # 일반구 분해행 스킵(첫 합계행만)
                if not r["cands"] or _is_num(r["cands"][0]["name"]):
                    continue
                seen.add(r["sigungu"])
                sgcode, sgname = match_sigungu(rlist, short, r["sigungu"], r["sigungu"])
                if not sgcode:
                    nmiss += 1; miss.add((short, r["sigungu"])); continue
                # 이 시군구의 기존 기초단체장(위키 등) 제거 후 역대 전체후보로 교체
                cur.execute("DELETE FROM results WHERE election_id=? AND region_code=? AND candidate_id IN "
                            "(SELECT id FROM candidates WHERE election_id=? AND office=? AND region_code=?)",
                            (hoe, sgcode, hoe, OFFICE, sgcode))
                cur.execute("DELETE FROM candidates WHERE election_id=? AND office=? AND region_code=?",
                            (hoe, OFFICE, sgcode))
                nreg += 1
                win = max((c["votes"] or 0) for c in r["cands"])
                for c in r["cands"]:
                    pid = resolve_party(cur, c["party"], hoe)
                    elected = 1 if (c["votes"] or 0) == win else 0
                    cur.execute(
                        "INSERT INTO candidates(election_id,office,region_code,name,party_id,is_elected)"
                        " VALUES (?,?,?,?,?,?)", (hoe, OFFICE, sgcode, c["name"], pid, elected))
                    cid = cur.lastrowid
                    cur.execute(
                        "INSERT INTO results(election_id,level,region_code,candidate_id,votes,vote_rate)"
                        " VALUES (?,?,?,?,?,?)", (hoe, "구시군", sgcode, cid, c["votes"], c["rate"]))
                    ncand += 1; nwin += elected
            time.sleep(0.1)
        con.commit()
        print(f"{hoe}회 기초단체장(역대): 경합시군구 {nreg} / 후보 {ncand} / 당선 {nwin} / 미매칭 {nmiss}"
              + (f" {sorted(miss)[:6]}" if miss else ""))
    con.close()


if __name__ == "__main__":
    main()
