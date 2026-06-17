"""민선 1·2회(1995·1998) 광역의원(시도의원) 지역구+비례 -> council 적재.

소스: data/raw/nec_hist_council12.json (info.nec.go.kr 역대선거 당선인명부, 당선자만).
1·2회는 OpenAPI 미지원(3회부터)이라 역대선거 통계시스템이 유일 소스.
당시 시군구는 현재 regions와 달라 sigungu_code 미매칭 다수(광역 종합은 시도 단위라 무영향).
실행: python backend/data_pipeline/ingest_council_12.py
"""
import json
import pathlib
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from ingest_council import build_region_list, match_sigungu  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DB = ROOT / "backend" / "db" / "election.sqlite"
RAW = ROOT / "data" / "raw" / "nec_hist_council12.json"


def main():
    d = json.loads(RAW.read_text(encoding="utf-8"))
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS council(
      hoecha INT, sgtype INT, sido TEXT, sigungu_code TEXT, sigungu_name TEXT,
      sgg TEXT, idx INT, party TEXT, name TEXT, votes INT, rate REAL, elected INT);
    CREATE INDEX IF NOT EXISTS idx_council ON council(hoecha, sigungu_code, sgtype);
    """)
    cur.execute("DELETE FROM council WHERE hoecha IN (1,2) AND sgtype IN (5,8)")
    rlist = build_region_list(con)

    # 지역구(sgtype 5)
    nreg = nmiss = 0
    idxmap = {}
    import re as _re
    for r in d["rows"]:
        sgcode, sgname = match_sigungu(rlist, r["sido"], r["sgname"], r.get("sigungu"))
        if not sgcode:
            nmiss += 1
        key = (r["hoecha"], r["sido_std"])
        i = idxmap.get(key, 0); idxmap[key] = i + 1
        # 1·2회 표기 '동해시제1' → '동해시제1선거구'(선거구 접미 보정)
        disp = r["sgname"]
        if _re.search(r"제\d+$", disp):
            disp += "선거구"
        cur.execute("INSERT INTO council VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (r["hoecha"], 5, r["sido"], sgcode, sgname, disp, i,
                     r["party"], r["name"], r.get("votes"), r.get("rate"), 1))
        nreg += 1

    # 비례(sgtype 8)
    npr = 0
    pidx = {}
    for r in d.get("pr", []):
        key = (r["hoecha"], r["sido_std"])
        i = pidx.get(key, 0); pidx[key] = i + 1
        cur.execute("INSERT INTO council VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (r["hoecha"], 8, r["sido"], None, None, "비례대표", i,
                     r["party"], r["name"], None, None, 1))
        npr += 1

    con.commit()
    print(f"지역구(sgtype5): {nreg} (시군구미매칭 {nmiss}) / 비례(sgtype8): {npr}")
    for hoe in (1, 2):
        for row in cur.execute("""SELECT sgtype, COUNT(*) FROM council
                                  WHERE hoecha=? AND sgtype IN (5,8) GROUP BY sgtype""", (hoe,)):
            print(f"  {hoe}회 sgtype{row[0]}: {row[1]}")
        for row in cur.execute("""SELECT party, COUNT(*) FROM council
                                  WHERE hoecha=? AND elected=1 GROUP BY party ORDER BY 2 DESC LIMIT 5""", (hoe,)):
            print(f"      {row[0]}: {row[1]}")
    con.close()


if __name__ == "__main__":
    main()
