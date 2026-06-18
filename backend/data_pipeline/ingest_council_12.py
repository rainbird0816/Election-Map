"""민선 1·2회(1995·1998) 광역의원(시도의원) '비례대표' -> council(sgtype=8) 적재.

소스: data/raw/nec_hist_council12.json (info.nec.go.kr 역대선거 당선인명부, 당선자만).
지역구(sgtype=5)는 낙선자 포함 적재를 위해 ingest_council_results_12.py 가 담당한다
(개표현황 VCCP09 선거구별 통계). 이 스크립트는 비례(8)만 적재 — 비례는 1·2회 모두
정당투표 미도입이라 당선인명부가 유일 소스라 당선자만 존재.
1·2회는 OpenAPI 미지원(3회부터)이라 역대선거 통계시스템이 유일 소스.
실행: python backend/data_pipeline/ingest_council_12.py
"""
import json
import pathlib
import sqlite3

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
    cur.execute("DELETE FROM council WHERE hoecha IN (1,2) AND sgtype=8")

    # 비례(sgtype 8) — 당선인명부(당선자만). 지역구(5)는 ingest_council_results_12.py.
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
    print(f"비례(sgtype8): {npr}")
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
