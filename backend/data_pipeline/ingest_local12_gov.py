"""민선 1·2회(1995·1998) 광역단체장 후보 전원(낙선 포함) -> candidates/results.

기존 ingest.py(metro_governors.json)는 1·2회 당선자만 적재. 본 스크립트는 이미 적재된
metro_sgg(office='광역단체장', 시군구별 후보 전원, ingest_metro_sgg_12.py)를 시도 단위로
합산해 후보 전원을 candidates/results 로 교체. 이후 precompute.py 로 summary 재생성.
실행: python backend/data_pipeline/ingest_local12_gov.py  (이후 precompute.py)
"""
import pathlib
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from ingest import resolve_party  # noqa: E402

DB = pathlib.Path(__file__).resolve().parent.parent / "db" / "election.sqlite"
OFFICE = "광역단체장"
SIDO_CODE = {
    "서울": "11", "부산": "26", "대구": "27", "인천": "28", "광주": "29", "대전": "30",
    "울산": "31", "세종": "36", "경기": "41", "강원": "42", "충북": "43", "충남": "44",
    "전북": "45", "전남": "46", "경북": "47", "경남": "48", "제주": "50",
}


def main():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    # 시도별 후보 합산: (hoecha, sido, party, name) -> votes
    rows = cur.execute(
        "SELECT hoecha, sido, party, name, SUM(votes) FROM metro_sgg "
        "WHERE hoecha IN (1,2) AND office=? GROUP BY hoecha, sido, party, name",
        (OFFICE,)).fetchall()
    if not rows:
        print("metro_sgg 1·2회 광역단체장 없음 — ingest_metro_sgg_12.py 먼저 실행")
        return

    # (hoecha, sido) 그룹 + 최다득표=당선
    by = {}
    for hoe, sido, party, name, votes in rows:
        by.setdefault((hoe, sido), []).append({"party": party, "name": name, "votes": votes or 0})

    # metro_sgg로 새로 채울 (회차,시도)만 제거(제주 등 미커버 시도는 metro_governors 당선자 유지)
    for (hoe, sido) in by:
        code = SIDO_CODE.get(sido)
        if not code:
            continue
        cur.execute("DELETE FROM results WHERE election_id=? AND region_code=? AND candidate_id IN "
                    "(SELECT id FROM candidates WHERE election_id=? AND office=? AND region_code=?)",
                    (hoe, code, hoe, OFFICE, code))
        cur.execute("DELETE FROM candidates WHERE election_id=? AND office=? AND region_code=?",
                    (hoe, OFFICE, code))
    nins = nelec = 0
    for (hoe, sido), cands in by.items():
        code = SIDO_CODE.get(sido)
        if not code:
            continue
        tot = sum(c["votes"] for c in cands) or 1
        win = max(c["votes"] for c in cands)
        for c in cands:
            pid = resolve_party(cur, c["party"], hoe)
            elected = 1 if c["votes"] == win else 0
            cur.execute(
                "INSERT INTO candidates(election_id,office,region_code,name,party_id,is_elected)"
                " VALUES (?,?,?,?,?,?)", (hoe, OFFICE, code, c["name"], pid, elected))
            cid = cur.lastrowid
            cur.execute(
                "INSERT INTO results(election_id,level,region_code,candidate_id,votes,vote_rate)"
                " VALUES (?,?,?,?,?,?)",
                (hoe, "시도", code, cid, c["votes"], round(c["votes"] / tot * 100, 2)))
            nins += 1
            nelec += elected
    con.commit()
    print(f"1·2회 광역단체장 후보 전원 적재: {nins} (당선 {nelec})")
    print("→ precompute.py 실행 필요")
    con.close()


if __name__ == "__main__":
    main()
