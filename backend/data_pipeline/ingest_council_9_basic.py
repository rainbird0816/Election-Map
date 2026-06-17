"""제9회(2026) 기초의원(구·시·군의원) 지역구+비례 -> council 테이블 적재.

소스(info.nec.go.kr 잠정):
  data/raw/nec9_ec6.json       지역구 개표결과(경합 선거구 후보 전원)
  data/raw/nec9_ec6_win.json   지역구 당선인 명부(무투표 포함)
  data/raw/nec9_ec9_win.json   기초의원 비례 당선인 명부(구시군별)

광역(5/8)은 ingest_council_9.py. 본 스크립트는 기초(sgtype 6/9)만.
실행: python backend/data_pipeline/ingest_council_9_basic.py
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

STD2SHORT = {
    "11": "서울", "26": "부산", "27": "대구", "28": "인천", "29": "광주", "30": "대전",
    "31": "울산", "36": "세종", "41": "경기", "42": "강원", "43": "충북", "44": "충남",
    "45": "전북", "46": "전남", "47": "경북", "48": "경남", "50": "제주",
}


def main():
    tally = json.loads((RAW / "nec9_ec6.json").read_text(encoding="utf-8"))
    win6 = json.loads((RAW / "nec9_ec6_win.json").read_text(encoding="utf-8"))["winners"]
    win9 = json.loads((RAW / "nec9_ec9_win.json").read_text(encoding="utf-8"))["winners"]

    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("DELETE FROM council WHERE hoecha=? AND sgtype IN (6,9)", (HOE,))
    rlist = build_region_list(con)

    # 1) 기초의원 지역구(sgtype 6): 경합 선거구 후보 전원
    winset = {(w["sido_std"], w["sgname"], w["name"]) for w in win6}
    tally_sgg = set()
    nins = nwin = nmiss = 0
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
                        (HOE, 6, short, sgcode, sgname, r["sgname"], i,
                         c["party"], c["name"], c["votes"], c["rate"], elected))
            nins += 1
            nwin += elected

    # 2) 무투표/누락 선거구 당선자만 명부에서 추가
    for w in win6:
        if (w["sido_std"], w["sgname"]) in tally_sgg:
            continue
        short = STD2SHORT[w["sido_std"]]
        sgcode, sgname = match_sigungu(rlist, short, w["sgname"], w.get("sigungu"))
        if not sgcode:
            nmiss += 1
        cur.execute("INSERT INTO council VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (HOE, 6, short, sgcode, sgname, w["sgname"], 0,
                     w["party"], w["name"], w["votes"], w["rate"], 1))
        nins += 1
        nwin += 1

    # 3) 기초비례(sgtype 9): 구시군별 당선자
    npr = nprmiss = 0
    pr_idx = {}
    for w in win9:
        short = STD2SHORT[w["sido_std"]]
        sgcode, sgname = match_sigungu(rlist, short, w["sigungu"], w["sigungu"])
        if not sgcode:
            nprmiss += 1
        key = (w["sido_std"], w["sigungu"])
        i = pr_idx.get(key, 0)
        pr_idx[key] = i + 1
        cur.execute("INSERT INTO council VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (HOE, 9, short, sgcode, sgname, "비례대표", i,
                     w["party"], w["name"], None, None, 1))
        npr += 1

    con.commit()
    print(f"기초의원 지역구(sgtype6): 행 {nins} / 당선 {nwin} / 선거구미매칭 {nmiss}")
    print(f"기초비례(sgtype9): 당선 {npr} / 미매칭 {nprmiss}")
    for row in cur.execute("""SELECT sgtype, COUNT(*), SUM(elected) FROM council
                              WHERE hoecha=? AND sgtype IN (6,9) GROUP BY sgtype""", (HOE,)):
        print(f"  sgtype {row[0]}: 행 {row[1]} / 당선 {row[2]}")
    con.close()


if __name__ == "__main__":
    main()
