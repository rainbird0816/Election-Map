# -*- coding: utf-8 -*-
"""민선 1·2회(1995·1998) 광역의원(시도의원) 지역구 '후보 전원(낙선 포함)' -> council(sgtype=5).

기존 ingest_council_12.py 는 역대선거 '당선인명부(당선자만)'만 적재해 낙선자가 없었다.
이 스크립트는 역대선거 개표현황 VCCP09 '선거구별' 통계표(statementId=VCCP09_#2,
electionType=5, electionCode=5)에서 선거구별 후보 전원의 득표를 받아 낙선자까지 적재한다.
- 경합 선거구: 개표현황에서 후보 전원 득표 → 최다 득표자 elected=1, 나머지 0.
- 무투표 당선 선거구: 개표가 없어 개표현황에 부재 → 당선인명부 JSON 으로 보완(elected=1, 득표 null).
선거구명(예 '종로구제1')은 당선인명부 sgname 과 동일 체계라 그대로 매칭/표기.
sgtype=8(광역비례)는 건드리지 않는다(ingest_council_12.py 가 적재).
실행: python backend/data_pipeline/ingest_council_results_12.py
"""
import io
import json
import pathlib
import re
import sqlite3
import sys
import time
import warnings

import httpx
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from ingest_council import build_region_list, match_sigungu  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DB = ROOT / "backend" / "db" / "election.sqlite"
RAW = ROOT / "data" / "raw" / "nec_hist_council12.json"
BASE = "https://info.nec.go.kr"
HDR = {"User-Agent": "Mozilla/5.0"}
HOE_ENAME = {1: "19950627", 2: "19980604"}
STD2SHORT = {
    "11": "서울", "26": "부산", "27": "대구", "28": "인천", "29": "광주", "30": "대전",
    "31": "울산", "41": "경기", "42": "강원", "43": "충북", "44": "충남",
    "45": "전북", "46": "전남", "47": "경북", "48": "경남", "50": "제주",
}


def _i(v):
    try:
        return int(v) if pd.notna(v) else None
    except (ValueError, TypeError):
        return None


def _f(v):
    try:
        return float(v) if pd.notna(v) else None
    except (ValueError, TypeError):
        return None


def fetch(cli, ename, city):
    data = {
        "electionId": "0000000000", "requestURI": "/electioninfo/0000000000/vc/vccp09.jsp",
        "topMenuId": "VC", "secondMenuId": "VCCP09", "menuId": "VCCP09",
        "statementId": "VCCP09_#2", "oldElectionType": "0", "electionType": "5",
        "electionName": ename, "electionCode": "5", "cityCode": city,
        "sggCityCode": "0", "townCode": "-1", "sggTownCode": "0",
    }
    return cli.post(f"{BASE}/electioninfo/electionInfo_report.xhtml", data=data).text


def parse(html):
    """선거구별 개표표 -> [{sgname, sigungu, cands:[(party,name,votes,rate)]}]. 각 선거구 '합계' 블록만."""
    try:
        df = pd.read_html(io.StringIO(html))[0]
    except (ValueError, IndexError):
        return []
    v = df.values.tolist()
    n = len(v)
    out = []
    for i in range(n - 1):
        sg = v[i][0]
        nxt = v[i + 1][1]
        if not (isinstance(sg, str) and sg.strip()):
            continue
        if not (isinstance(nxt, str) and nxt.strip() == "합계"):
            continue  # 후보 득표 집계는 '합계' 블록에만; 시군구 블록은 스킵
        sgname = sg.strip()
        sigungu = None
        if i + 4 < n and isinstance(v[i + 4][1], str) and v[i + 4][1].strip() not in ("합계", "계", ""):
            sigungu = v[i + 4][1].strip()
        hdr, vote = v[i], v[i + 1]
        rate = v[i + 2] if i + 2 < n else [None] * len(hdr)
        cands = []
        for j in range(4, len(hdr)):
            lab = hdr[j]
            if not (isinstance(lab, str) and lab.strip()):
                continue
            ls = lab.strip()
            if " " not in ls:  # 후보 라벨은 '정당 이름'(공백 1개); '계' 등 집계열 제외
                continue       # (이름에 '기권'·'투표' 등이 들어가도 오제외 안 됨)
            parts = ls.rsplit(" ", 1)
            party, name = (parts[0], parts[1]) if len(parts) == 2 else (ls, None)
            cands.append((party, name, _i(vote[j]), _f(rate[j])))
        if cands:
            out.append({"sgname": sgname, "sigungu": sigungu, "cands": cands})
    return out


def disp_name(sgname):
    """'종로구제1' -> '종로구제1선거구' (당선인명부 적재와 동일 표기 보정)."""
    return sgname + "선거구" if re.search(r"제\d+$", sgname) else sgname


def main():
    cli = httpx.Client(timeout=60, verify=False, headers=HDR, follow_redirects=True)
    cli.get(f"{BASE}/main/showDocument.xhtml?electionId=0000000000&topMenuId=VC&secondMenuId=VCCP09")
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS council(
      hoecha INT, sgtype INT, sido TEXT, sigungu_code TEXT, sigungu_name TEXT,
      sgg TEXT, idx INT, party TEXT, name TEXT, votes INT, rate REAL, elected INT);
    CREATE INDEX IF NOT EXISTS idx_council ON council(hoecha, sigungu_code, sgtype);
    """)
    rlist = build_region_list(con)
    jd = json.loads(RAW.read_text(encoding="utf-8"))

    for hoe, ename in HOE_ENAME.items():
        jwin = {}  # (sido, sgname) -> json row(당선자)
        for r in jd["rows"]:
            if r["hoecha"] == hoe:
                jwin[(r["sido"], r["sgname"])] = r

        cur.execute("DELETE FROM council WHERE hoecha=? AND sgtype=5", (hoe,))
        idxmap = {}
        ncand = nwin = nmiss = nunc = 0
        scraped_keys = set()
        win_conflict = []

        for city, short in STD2SHORT.items():
            for rc in parse(fetch(cli, ename, city)):
                key = (short, rc["sgname"])
                scraped_keys.add(key)
                sgcode, sgname_m = match_sigungu(rlist, short, rc["sgname"], rc["sigungu"])
                if not sgcode:
                    nmiss += 1
                win = max(rc["cands"], key=lambda c: c[2] if c[2] is not None else -1)
                jw = jwin.get(key)
                if jw and jw["name"] != win[1]:
                    win_conflict.append((short, rc["sgname"], jw["name"], jw["party"], win[1], win[0]))
                for party, name, votes, rate in rc["cands"]:
                    i = idxmap.get(short, 0); idxmap[short] = i + 1
                    elected = 1 if (name == win[1] and party == win[0]) else 0
                    cur.execute("INSERT INTO council VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                                (hoe, 5, short, sgcode, sgname_m, disp_name(rc["sgname"]), i,
                                 party, name, votes, rate, elected))
                    ncand += 1
                    nwin += elected
            time.sleep(0.1)

        # 무투표 당선(개표현황 부재) 선거구를 당선인명부로 보완
        for (sido, sgname), r in jwin.items():
            if (sido, sgname) in scraped_keys:
                continue
            sgcode, sgname_m = match_sigungu(rlist, sido, sgname, r.get("sigungu"))
            if not sgcode:
                nmiss += 1
            i = idxmap.get(sido, 0); idxmap[sido] = i + 1
            cur.execute("INSERT INTO council VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                        (hoe, 5, sido, sgcode, sgname_m, disp_name(sgname), i,
                         r["party"], r["name"], r.get("votes"), r.get("rate"), 1))
            ncand += 1; nwin += 1; nunc += 1

        con.commit()
        # 검증: 당선인명부의 모든 당선자가 elected=1 로 존재하는가
        elected_names = {(rr[0], rr[1]) for rr in cur.execute(
            "SELECT sido, name FROM council WHERE hoecha=? AND sgtype=5 AND elected=1", (hoe,))}
        json_names = {(r["sido"], r["name"]) for r in jd["rows"] if r["hoecha"] == hoe}
        missing_win = json_names - elected_names
        print(f"=== {hoe}회 ({ename}) ===")
        print(f"  후보(낙선포함) {ncand} / 당선 {nwin} (무투표보완 {nunc}) / 시군구미매칭 {nmiss}")
        print(f"  당선인명부 {len(json_names)}명 중 미커버 {len(missing_win)}, 개표상위≠명부당선 {len(win_conflict)}")
        for m in list(missing_win)[:10]:
            print(f"    [미커버] {m}")
        for c in win_conflict[:10]:
            print(f"    [당선상충] {c[0]} {c[1]}: 명부={c[2]}({c[3]}) vs 개표1위={c[4]}({c[5]})")
    con.close()


if __name__ == "__main__":
    main()
