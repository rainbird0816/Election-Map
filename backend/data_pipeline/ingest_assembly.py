"""국회의원(총선) 시도별 지역구 의석 -> elections + region_election_summary.

시도 채색 = 지역구 의석 최다 정당. top_parties_json = [{party,color,seats}] (의석순).
개별 후보/results 없음(시도 집계 슬라이스). 선행: init_db, ingest(정당 시드).
실행: python backend/data_pipeline/ingest_assembly.py
"""
import json
import sqlite3
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DB = ROOT / "backend" / "db" / "election.sqlite"
RAW = ROOT / "data" / "raw" / "national_assembly.json"
OFFICE = "국회의원"

SIDO_CODE = {
    "서울": "11", "부산": "26", "대구": "27", "인천": "28", "광주": "29",
    "대전": "30", "울산": "31", "세종": "36", "경기": "41", "강원": "42",
    "충북": "43", "충남": "44", "전북": "45", "전남": "46", "경북": "47",
    "경남": "48", "제주": "50",
}
NEW_COLORS = {
    "새로운미래": "#00B0A6", "개혁신당": "#FF7920",
    # 13~19대 역대 정당
    "민주정의당": "#003A82", "통일민주당": "#E5A000", "평화민주당": "#009E4F",
    "신민주공화당": "#006B9F", "민주자유당": "#0000CD", "통일국민당": "#FFCC00",
    "신정치개혁당": "#9E9E9E", "신한국당": "#0F4DA8", "새정치국민회의": "#00A0A0",
    "국민통합21": "#FF6600", "창조한국당": "#FFA500",
}


def resolve_party(cur, name):
    """정당명 -> (id, color). 미등록은 lineage 7로 생성."""
    row = cur.execute("SELECT id, color_hex FROM parties WHERE name=?", (name,)).fetchone()
    if row:
        return row[0], row[1]
    color = NEW_COLORS.get(name, "#9E9E9E")
    cur.execute("INSERT INTO parties(name,lineage_id,color_hex) VALUES (?,7,?)", (name, color))
    return cur.lastrowid, color


def main():
    data = json.loads(RAW.read_text(encoding="utf-8"))
    con = sqlite3.connect(DB)
    cur = con.cursor()

    ids = [e["id"] for e in data["elections"]]
    qm = ",".join("?" * len(ids))
    cur.execute(f"DELETE FROM region_election_summary WHERE election_id IN ({qm})", ids)
    cur.execute(f"DELETE FROM elections WHERE id IN ({qm})", ids)

    for e in data["elections"]:
        cur.execute(
            "INSERT INTO elections(id,type,name,hoecha,election_date) VALUES (?,?,?,?,?)",
            (e["id"], "총선", e["name"], e["daesu"], e["date"]),
        )

    # (election_id, sido) -> [{party,color,seats,party_id}]
    grouped = {}
    for s in data["seats"]:
        pid, color = resolve_party(cur, s["party"])
        key = (s["election_id"], SIDO_CODE[s["sido"]])
        grouped.setdefault(key, []).append(
            {"party": s["party"], "color": color, "seats": s["seats"], "party_id": pid}
        )

    n = 0
    for (eid, code), parties in grouped.items():
        parties.sort(key=lambda x: x["seats"], reverse=True)
        win = parties[0]
        top_json = json.dumps(
            [{"party": p["party"], "color": p["color"], "seats": p["seats"]} for p in parties],
            ensure_ascii=False,
        )
        cur.execute(
            """INSERT INTO region_election_summary
               (region_code, election_id, office, winner_candidate_id,
                winner_party_id, winner_rate, turnout, top_parties_json)
               VALUES (?,?,?,?,?,?,?,?)""",
            (code, eid, OFFICE, None, win["party_id"], None, None, top_json),
        )
        n += 1

    con.commit()
    print(f"총선 elections: {len(ids)}")
    print(f"국회의원 summary(시도): {n}")
    for eid in ids:
        c = cur.execute(
            "SELECT COUNT(*) FROM region_election_summary WHERE election_id=? AND office=?",
            (eid, OFFICE),
        ).fetchone()[0]
        print(f"  election {eid}: {c} 시도")
    con.close()


if __name__ == "__main__":
    main()
