"""시도교육감 -> region_election_summary (office='교육감').

교육감은 정당 없음 → 성향(진보/보수/중도)을 pseudo-party로 만들어 채색.
교육감 이름은 top_parties_json에 저장({name, lean}).
precompute 다음에 실행(region_election_summary를 precompute가 비우므로).
실행: python backend/data_pipeline/ingest_superintendent.py
"""
import json
import sqlite3
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DB = ROOT / "backend" / "db" / "election.sqlite"
RAW = ROOT / "data" / "raw" / "superintendents.json"
OFFICE = "교육감"

SIDO_CODE = {
    "서울": "11", "부산": "26", "대구": "27", "인천": "28", "광주": "29",
    "대전": "30", "울산": "31", "세종": "36", "경기": "41", "강원": "42",
    "충북": "43", "충남": "44", "전북": "45", "전남": "46", "경북": "47",
    "경남": "48", "제주": "50",
}


def lean_party(cur, lean, color):
    """성향 -> pseudo-party id (이름 '교육감-진보' 등, lineage 7)."""
    name = f"교육감({lean})"
    row = cur.execute("SELECT id FROM parties WHERE name=?", (name,)).fetchone()
    if row:
        return row[0]
    cur.execute("INSERT INTO parties(name,lineage_id,color_hex) VALUES (?,7,?)", (name, color))
    return cur.lastrowid


def main():
    data = json.loads(RAW.read_text(encoding="utf-8"))
    lc = data["lean_color"]
    con = sqlite3.connect(DB)
    cur = con.cursor()

    cur.execute("DELETE FROM region_election_summary WHERE office=?", (OFFICE,))

    n = 0
    for r in data["rows"]:
        eid = r["hoecha"]  # 지선 election id = 회차
        code = SIDO_CODE[r["sido"]]
        lean = r["lean"]
        color = lc.get(lean, "#9E9E9E")
        pid = lean_party(cur, lean, color)
        top = json.dumps([{"name": r["name"], "lean": lean, "color": color}], ensure_ascii=False)
        cur.execute(
            """INSERT INTO region_election_summary
               (region_code, election_id, office, winner_candidate_id,
                winner_party_id, winner_rate, turnout, top_parties_json)
               VALUES (?,?,?,?,?,?,?,?)""",
            (code, eid, OFFICE, None, pid, None, None, top),
        )
        n += 1

    con.commit()
    print(f"교육감 summary: {n}")
    for eid in (5, 6, 7, 8):
        c = cur.execute("SELECT COUNT(*) FROM region_election_summary WHERE election_id=? AND office=?", (eid, OFFICE)).fetchone()[0]
        print(f"  {eid}회: {c}")
    con.close()


if __name__ == "__main__":
    main()
