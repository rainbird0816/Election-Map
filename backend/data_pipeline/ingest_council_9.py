"""제9회(2026) 광역의원(시도의원) 지역구+비례 -> council 테이블 적재.

소스(info.nec.go.kr 잠정, 정제본 공개 시 교체):
  data/raw/nec9_ec5.json       지역구 개표결과(경합 선거구 후보 전원)
  data/raw/nec9_ec5_win.json   지역구 당선인 명부(무투표 포함)
  data/raw/nec9_ec8_win.json   비례 당선인 명부

지역구: 광주(29)/전남(46) 분리. 비례: 전남광주통합특별시(임시코드 49) 단일.
당선 = 당선인 명부 기준. 개표결과에 없는 선거구(무투표/누락)는 명부 당선자만 추가.
실행: python backend/data_pipeline/ingest_council_9.py
"""
import json
import pathlib
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from ingest_council import build_region_list, match_sigungu  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DB = ROOT / "backend" / "db" / "election.sqlite"
RAW = ROOT / "data" / "raw"
HOE = 9

# 행정표준 시도코드 -> 약칭(council.sido 표기 + region 매칭용)
STD2SHORT = {
    "11": "서울", "26": "부산", "27": "대구", "28": "인천", "29": "광주", "30": "대전",
    "31": "울산", "36": "세종", "41": "경기", "42": "강원", "43": "충북", "44": "충남",
    "45": "전북", "46": "전남", "47": "경북", "48": "경남", "50": "제주",
    "49": "전남광주통합",
}


def main():
    tally = json.loads((RAW / "nec9_ec5.json").read_text(encoding="utf-8"))
    win5 = json.loads((RAW / "nec9_ec5_win.json").read_text(encoding="utf-8"))["winners"]
    win8 = json.loads((RAW / "nec9_ec8_win.json").read_text(encoding="utf-8"))["winners"]

    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS council(
      hoecha INT, sgtype INT, sido TEXT, sigungu_code TEXT, sigungu_name TEXT,
      sgg TEXT, idx INT, party TEXT, name TEXT, votes INT, rate REAL, elected INT);
    CREATE INDEX IF NOT EXISTS idx_council ON council(hoecha, sigungu_code, sgtype);
    """)
    cur.execute("DELETE FROM council WHERE hoecha=? AND sgtype IN (5,8)", (HOE,))
    rlist = build_region_list(con)

    # 당선자 집합 (개표결과 경합 선거구의 elected 표시용)
    winset = {(w["sido_std"], w["sgname"], w["name"]) for w in win5}
    nins = nwin = nmiss = 0

    # 1) 지역구 경합 선거구: 후보 전원 적재
    tally_sgg = set()
    for r in tally["rows"]:
        std = r["sido_std"]
        short = STD2SHORT[std]
        tally_sgg.add((std, r["sgname"]))
        sgcode, sgname = match_sigungu(rlist, short, r["sgname"], r.get("sigungu"))
        if not sgcode:
            nmiss += 1
        for i, c in enumerate(r["cands"]):
            elected = 1 if (std, r["sgname"], c["name"]) in winset else 0
            cur.execute("INSERT INTO council VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                        (HOE, 5, short, sgcode, sgname, r["sgname"], i,
                         c["party"], c["name"], c["votes"], c["rate"], elected))
            nins += 1
            nwin += elected

    # 2) 개표결과에 없는 선거구(무투표/누락)의 당선자만 명부에서 추가
    for w in win5:
        if (w["sido_std"], w["sgname"]) in tally_sgg:
            continue
        short = STD2SHORT[w["sido_std"]]
        sgcode, sgname = match_sigungu(rlist, short, w["sgname"], w.get("sigungu"))
        if not sgcode:
            nmiss += 1
        cur.execute("INSERT INTO council VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (HOE, 5, short, sgcode, sgname, w["sgname"], 0,
                     w["party"], w["name"], w["votes"], w["rate"], 1))
        nins += 1
        nwin += 1

    # 3) 비례 당선자 (sgtype 8, 시도 단위)
    npr = 0
    pr_idx = {}
    for w in win8:
        short = STD2SHORT[w["sido_std"]]
        i = pr_idx.get(w["sido_std"], 0)
        pr_idx[w["sido_std"]] = i + 1
        cur.execute("INSERT INTO council VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (HOE, 8, short, None, None, "비례대표", i,
                     w["party"], w["name"], None, None, 1))
        npr += 1

    con.commit()
    print(f"지역구(sgtype5): 행 {nins} / 당선 {nwin} / 시군구미매칭 {nmiss}")
    print(f"비례(sgtype8): 당선 {npr}")
    tot_win = cur.execute("SELECT COUNT(*) FROM council WHERE hoecha=? AND elected=1", (HOE,)).fetchone()[0]
    print(f"9회 광역의원 총 당선: {tot_win} (지역구+비례)")
    for row in cur.execute("""SELECT party, COUNT(*) FROM council
                              WHERE hoecha=? AND elected=1 GROUP BY party ORDER BY 2 DESC""", (HOE,)):
        print(f"  {row[0]}: {row[1]}")
    con.close()


if __name__ == "__main__":
    main()
