"""제9회(2026) 시군구별 광역단체장(ec3)·광역비례(ec8) 득표 -> metro_sgg 적재.

소스(info.nec.go.kr 개표진행상황, 잠정):
  data/raw/nec9_ec3_sgg.json   광역단체장 시군구별 후보 득표
  data/raw/nec9_ec8_sgg.json   광역비례 시군구별 정당 득표
3~8회는 ingest_metro_sgg.py(OpenAPI). 9회는 OpenAPI 미공개라 본 스크립트.
세종/일반구 등 읍면동 단위 행은 match_sigungu로 상위 시군구에 합산(rate 재계산).
실행: python backend/data_pipeline/ingest_metro_sgg_9.py
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


def ingest_office(cur, rlist, path, office, has_cand):
    rows = json.loads(path.read_text(encoding="utf-8"))["rows"]
    agg = {}      # key -> votes (key: (sgcode,party[,name]))
    meta = {}     # sgcode -> (short, sgname)
    miss = set()
    for r in rows:
        short = STD2SHORT.get(r["sido_std"])
        sgcode, sgname = match_sigungu(rlist, short, r["sigungu"], r["sigungu"])
        if not sgcode:
            miss.add((short, r["sigungu"]))
            continue
        key = (sgcode, r["party"], r.get("name")) if has_cand else (sgcode, r["party"])
        agg[key] = agg.get(key, 0) + (r.get("votes") or 0)
        meta[sgcode] = (short, sgname)

    tot = {}
    for key, v in agg.items():
        tot[key[0]] = tot.get(key[0], 0) + v

    n = 0
    for key, v in agg.items():
        sgcode = key[0]
        short, sgname = meta[sgcode]
        name = key[2] if has_cand else None
        rate = round(v / tot[sgcode] * 100, 2) if tot[sgcode] else None
        cur.execute(
            "INSERT INTO metro_sgg(hoecha,office,sido,sigungu_code,sigungu_name,party,name,votes,rate)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (HOE, office, short, sgcode, sgname, key[1], name, v, rate))
        n += 1
    nsgg = len({k[0] for k in agg})
    print(f"  {office}: {n}행 / 시군구 {nsgg} / 미매칭 {len(miss)}" +
          (f" {sorted(miss)[:8]}" if miss else ""))


def main():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS metro_sgg(
      hoecha INT, office TEXT, sido TEXT, sigungu_code TEXT, sigungu_name TEXT,
      party TEXT, name TEXT, votes INT, rate REAL);
    CREATE INDEX IF NOT EXISTS idx_metro_sgg ON metro_sgg(hoecha, sigungu_code, office);
    """)
    cur.execute("DELETE FROM metro_sgg WHERE hoecha=?", (HOE,))
    rlist = build_region_list(con)
    ingest_office(cur, rlist, RAW / "nec9_ec3_sgg.json", "광역단체장", True)
    ingest_office(cur, rlist, RAW / "nec9_ec8_sgg.json", "광역비례", False)
    con.commit()
    for row in cur.execute("SELECT office, COUNT(*), COUNT(DISTINCT sigungu_code) FROM metro_sgg WHERE hoecha=9 GROUP BY office"):
        print(f"metro_sgg 9회 {row[0]}: {row[1]}행 / 시군구 {row[2]}")
    con.close()


if __name__ == "__main__":
    main()
