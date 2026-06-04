"""results -> region_election_summary / elected_seats 생성 (광역단체장 + 기초단체장).
turnout(시도)은 raw JSON의 공식 시도별 투표율에서 보강. 시군구 turnout 은 NULL.
실행: python backend/data_pipeline/precompute.py
"""
import json
import sqlite3
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DB = ROOT / "backend" / "db" / "election.sqlite"
RAW = ROOT / "data" / "raw" / "metro_governors.json"

SIDO_CODE = {
    "서울": "11", "부산": "26", "대구": "27", "인천": "28", "광주": "29",
    "대전": "30", "울산": "31", "세종": "36", "경기": "41", "강원": "42",
    "충북": "43", "충남": "44", "전북": "45", "전남": "46", "경북": "47",
    "경남": "48", "제주": "50",
}


def load_turnout():
    data = json.loads(RAW.read_text(encoding="utf-8"))
    out = {}
    for hoecha, m in data.get("turnout", {}).items():
        for sido, val in m.items():
            out[(int(hoecha), SIDO_CODE[sido])] = val
    return out


def main():
    turnout = load_turnout()
    con = sqlite3.connect(DB)
    cur = con.cursor()

    cur.execute("DELETE FROM region_election_summary")
    cur.execute("DELETE FROM elected_seats")

    # 회차·지역별 상위 정당(득표율) — 광역/기초 모두
    top = {}
    for eid, code, pid, rate in cur.execute(
        """SELECT r.election_id, r.region_code, c.party_id, r.vote_rate
           FROM results r JOIN candidates c ON c.id=r.candidate_id
           WHERE r.vote_rate IS NOT NULL
           ORDER BY r.election_id, r.region_code, r.vote_rate DESC"""
    ):
        top.setdefault((eid, code), []).append({"party_id": pid, "rate": rate})

    # 당선자(최고 득표) — office/level 무관
    rows = cur.execute(
        """SELECT r.region_code, r.election_id, c.id, c.party_id, r.vote_rate, c.office
           FROM results r JOIN candidates c ON c.id=r.candidate_id
           WHERE c.is_elected=1"""
    ).fetchall()

    for code, eid, cand_id, party_id, rate, office in rows:
        t = turnout.get((eid, code))  # 시군구는 None
        top_json = json.dumps(top.get((eid, code), [])[:3], ensure_ascii=False)
        cur.execute(
            """INSERT INTO region_election_summary
               (region_code, election_id, office, winner_candidate_id,
                winner_party_id, winner_rate, turnout, top_parties_json)
               VALUES (?,?,?,?,?,?,?,?)""",
            (code, eid, office, cand_id, party_id, rate, t, top_json),
        )
        cur.execute(
            """INSERT INTO elected_seats(region_code, election_id, office, candidate_id)
               VALUES (?,?,?,?)""",
            (code, eid, office, cand_id),
        )

    con.commit()
    for office in ("광역단체장", "기초단체장"):
        n = cur.execute(
            "SELECT COUNT(*) FROM region_election_summary WHERE office=?", (office,)
        ).fetchone()[0]
        print(f"summary[{office}]: {n}")
    print(f"elected_seats: {cur.execute('SELECT COUNT(*) FROM elected_seats').fetchone()[0]}")
    con.close()


if __name__ == "__main__":
    main()
