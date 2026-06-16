"""민선 1·2회(1995·1998) 시군구별 광역단체장 후보 득표 -> metro_sgg(office='광역단체장').

소스: info.nec.go.kr 역대선거 개표현황(VCCP09, electionId=0000000000).
1·2회 광역의원 비례는 정당투표(1인2표) 미도입(2002 3회부터)이라 광역비례 시군구 득표는 원천 부재.
역대 개표현황 표는 후보명이 MultiIndex 컬럼 헤더(…, '민주자유당 정원식')에 있다.
세종/일반구 읍면동 행은 match_sigungu로 상위 시군구 합산.
실행: python backend/data_pipeline/ingest_metro_sgg_12.py
"""
import io
import pathlib
import sqlite3
import sys
import time
import warnings

import httpx
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from ingest_council import build_region_list, match_sigungu  # noqa: E402

DB = pathlib.Path(__file__).resolve().parent.parent / "db" / "election.sqlite"
BASE = "https://info.nec.go.kr"
HDR = {"User-Agent": "Mozilla/5.0"}
HOE_ENAME = {1: "19950627", 2: "19980604"}
STD2SHORT = {
    "11": "서울", "26": "부산", "27": "대구", "28": "인천", "29": "광주", "30": "대전",
    "31": "울산", "41": "경기", "42": "강원", "43": "충북", "44": "충남",
    "45": "전북", "46": "전남", "47": "경북", "48": "경남", "50": "제주",
}


def _num(v, cast):
    try:
        return cast(v) if pd.notna(v) else None
    except (ValueError, TypeError):
        return None


def fetch_gov(cli, ename, city):
    data = {
        "electionId": "0000000000", "requestURI": "/electioninfo/0000000000/vc/vccp09.jsp",
        "topMenuId": "VC", "secondMenuId": "VCCP09", "menuId": "VCCP09",
        "statementId": "VCCP09_#3", "oldElectionType": "0", "electionType": "4",
        "electionName": ename, "electionCode": "3", "cityCode": city,
        "sggCityCode": "0", "townCode": "-1", "sggTownCode": "0",
    }
    return cli.post(f"{BASE}/electioninfo/electionInfo_report.xhtml", data=data).text


def parse_gov(html):
    """역대 광역단체장 시군구 득표. 후보명=MultiIndex 컬럼 마지막 레벨. → [{sigungu,party,name,votes,rate}]."""
    try:
        df = pd.read_html(io.StringIO(html))[0]
    except (ValueError, IndexError):
        return []
    if not isinstance(df.columns, pd.MultiIndex):
        return []
    cands = {}
    for j, c in enumerate(df.columns):
        if c[0] != "후보자별 득표수":  # 후보 컬럼만(무효/기권/선거인수 등 제외)
            continue
        label = c[-1]
        if isinstance(label, str) and label != "계" and "득표" not in label:
            cands[j] = label
    df.columns = range(len(df.columns))
    rows = df.values.tolist()
    out = []
    for idx, r in enumerate(rows):
        sgu = r[0]
        if not (isinstance(sgu, str) and sgu.strip()) or sgu.strip() in ("합계", "계"):
            continue
        if pd.isna(r[1]):
            continue
        rr = rows[idx + 1] if idx + 1 < len(rows) else None
        for j, cand in cands.items():
            parts = cand.rsplit(" ", 1)
            party, name = (parts[0], parts[1]) if len(parts) == 2 else (cand, None)
            out.append({"sigungu": sgu.strip(), "party": party, "name": name,
                        "votes": _num(r[j], int), "rate": _num(rr[j] if rr else None, float)})
    return out


def main():
    cli = httpx.Client(timeout=60, verify=False, headers=HDR, follow_redirects=True)
    cli.get(f"{BASE}/main/showDocument.xhtml?electionId=0000000000&topMenuId=VC&secondMenuId=VCCP09")
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS metro_sgg(
      hoecha INT, office TEXT, sido TEXT, sigungu_code TEXT, sigungu_name TEXT,
      party TEXT, name TEXT, votes INT, rate REAL);
    CREATE INDEX IF NOT EXISTS idx_metro_sgg ON metro_sgg(hoecha, sigungu_code, office);
    """)
    rlist = build_region_list(con)

    for hoe, ename in HOE_ENAME.items():
        cur.execute("DELETE FROM metro_sgg WHERE hoecha=? AND office='광역단체장'", (hoe,))
        agg, meta, miss = {}, {}, set()
        for city, short in STD2SHORT.items():
            for d in parse_gov(fetch_gov(cli, ename, city)):
                sgcode, sgname = match_sigungu(rlist, short, d["sigungu"], d["sigungu"])
                if not sgcode:
                    miss.add((short, d["sigungu"]))
                    continue
                k = (sgcode, d["party"], d["name"])
                agg[k] = agg.get(k, 0) + (d["votes"] or 0)
                meta[sgcode] = (short, sgname)
            time.sleep(0.1)
        tot = {}
        for (sgcode, _, _), v in agg.items():
            tot[sgcode] = tot.get(sgcode, 0) + v
        n = 0
        for (sgcode, party, name), v in agg.items():
            short, sgname = meta[sgcode]
            rate = round(v / tot[sgcode] * 100, 2) if tot[sgcode] else None
            cur.execute(
                "INSERT INTO metro_sgg(hoecha,office,sido,sigungu_code,sigungu_name,party,name,votes,rate)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (hoe, "광역단체장", short, sgcode, sgname, party, name, v, rate))
            n += 1
        con.commit()
        nsgg = len({k[0] for k in agg})
        print(f"{hoe}회 광역단체장 시군구: {n}행 / 시군구 {nsgg} / 미매칭 {len(miss)}" +
              (f" {sorted(miss)[:8]}" if miss else ""))
    con.close()


if __name__ == "__main__":
    main()
