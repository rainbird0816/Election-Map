"""광역단체장 3~8회 개표결과(data/raw/metro_governors.json) -> SQLite.

원본은 data/raw/ 에 두고 디스크에서 읽는다(컨텍스트에 올리지 않음).
4~8회는 전체 후보(낙선 포함), 3회는 당선자만.
당선자 = (회차, 시도)별 최다 득표.
실행: python backend/data_pipeline/ingest.py
"""
import json
import sqlite3
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DB = ROOT / "backend" / "db" / "election.sqlite"
RAW = ROOT / "data" / "raw" / "metro_governors.json"
OFFICE = "광역단체장"

SIDO_CODE = {
    "서울": "11", "부산": "26", "대구": "27", "인천": "28", "광주": "29",
    "대전": "30", "울산": "31", "세종": "36", "경기": "41", "강원": "42",
    "충북": "43", "충남": "44", "전북": "45", "전남": "46", "경북": "47",
    "경남": "48", "제주": "50",
    "전남광주통합": "49",  # 9회(2026): 광주+전남 통합특별시(임시코드)
}

# 시드에 고정 id로 들어간 정당 (이름 -> id). '민주당'은 회차별 분기.
SEEDED = {
    "새천년민주당": 11, "열린우리당": 12, "새정치민주연합": 17, "더불어민주당": 18,
    "한나라당": 21, "새누리당": 22, "자유한국당": 23, "미래통합당": 24, "국민의힘": 25,
    "민주노동당": 31, "통합진보당": 32, "정의당": 33,
    "자유민주연합": 41, "자유선진당": 42, "국민의당": 51, "바른미래당": 52,
    "무소속": 61,
}
# 군소정당 자동등록 시 색상(lineage 7). 없으면 회색.
MINOR_COLORS = {
    "국민중심당": "#006666", "시민당": "#43A047", "한국의미래를준비하는당": "#FB8C00",
    "진보신당": "#D7003A", "국민참여당": "#F58220", "평화민주당": "#2E8B57",
    "미래연합": "#8E44AD", "노동당": "#E5007F", "새정치당": "#00897B",
    "민주평화당": "#00B5A5", "민중당": "#E50000", "녹색당": "#00A651",
    "가자코리아": "#6D4C41", "우리미래": "#5B2C9D", "대한애국당": "#003478",
    "친박연대": "#6A1B9A", "기본소득당": "#00D2C6", "진보당": "#D6001C",
    "통일한국당": "#5C6BC0",
    "녹색평화당": "#4CAF50", "사회당": "#E50000", "민주국민당": "#0000CD",
    "개혁신당": "#FF7210", "조국혁신당": "#0073CF", "여성의당": "#A50034",
    # 군소정당 색상 보강(2026-06-17): 회색→고유색(무소속 외 지역 채색)
    "국민연합": "#3949AB", "국민중심연합": "#0F8B8D", "신정치개혁당": "#7CB342",
    "민국당": "#C62828", "한국미래연합": "#9C27B0", "노년권익보호당": "#795548",
    "한미준": "#EF6C00", "자유평화당": "#26A69A", "국제녹색당": "#2E7D32",
    "겨레자유평화통일당": "#455A64", "공화당": "#AD1457", "한국국민당": "#1565C0",
    "한반도미래연합": "#6A1B9A", "코리아당": "#8D6E63", "국민대통합당": "#00838F",
    "한류연합당": "#D81B60", "우리공화당": "#B71C1C", "코리아": "#5D4037",
    "한국독립당": "#1B5E20", "친민당": "#AD1457", "한국당": "#C0392B",
}


def resolve_party(cur, name, hoecha):
    """정당명 -> party_id. 미등록 군소정당은 lineage 7로 자동 생성."""
    if name == "민주당":
        if hoecha in (1, 2):  # 1995 민주당(통합민주당) — 2006/2010 민주당과 별개
            row = cur.execute(
                "SELECT id FROM parties WHERE name='민주당' AND era_start='1991'").fetchone()
            if row:
                return row[0]
            cur.execute(
                "INSERT INTO parties(name,lineage_id,color_hex,era_start,era_end) "
                "VALUES ('민주당',1,'#73C03B','1991','1995')")
            return cur.lastrowid
        return 10 if hoecha == 4 else 15  # 4회=2006 민주당(10), 5회=2010 민주당(15)
    if name in SEEDED:
        return SEEDED[name]
    row = cur.execute("SELECT id FROM parties WHERE name=?", (name,)).fetchone()
    if row:
        return row[0]
    color = MINOR_COLORS.get(name, "#9E9E9E")
    cur.execute(
        "INSERT INTO parties(name,lineage_id,color_hex) VALUES (?,?,?)",
        (name, 7, color),
    )
    return cur.lastrowid


def main():
    data = json.loads(RAW.read_text(encoding="utf-8"))
    con = sqlite3.connect(DB)
    cur = con.cursor()

    # 멱등성: 기존 P1 적재분 제거 (election id 3~8)
    ids = [e["hoecha"] for e in data["elections"]]
    qmarks = ",".join("?" * len(ids))
    cur.execute(f"DELETE FROM results WHERE election_id IN ({qmarks})", ids)
    cur.execute(f"DELETE FROM candidates WHERE election_id IN ({qmarks})", ids)
    cur.execute(f"DELETE FROM elections WHERE id IN ({qmarks})", ids)

    for e in data["elections"]:
        cur.execute(
            "INSERT INTO elections(id,type,name,hoecha,election_date) VALUES (?,?,?,?,?)",
            (e["hoecha"], "지선", e["name"], e["hoecha"], e["date"]),
        )

    # (회차, 시도)별 최다 득표자 식별
    best = {}  # (hoecha, sido) -> max votes
    for c in data["candidates"]:
        key = (c["hoecha"], c["sido"])
        v = c.get("votes") or 0
        if key not in best or v > best[key]:
            best[key] = v

    n_cand = n_res = 0
    for c in data["candidates"]:
        eid = c["hoecha"]
        code = SIDO_CODE[c["sido"]]
        pid = resolve_party(cur, c["party"], eid)
        votes = c.get("votes")
        is_elected = 1 if (votes or 0) == best[(c["hoecha"], c["sido"])] else 0
        cur.execute(
            """INSERT INTO candidates(election_id,office,region_code,name,party_id,is_elected)
               VALUES (?,?,?,?,?,?)""",
            (eid, OFFICE, code, c["name"], pid, is_elected),
        )
        cid = cur.lastrowid
        n_cand += 1
        cur.execute(
            """INSERT INTO results(election_id,level,region_code,candidate_id,votes,vote_rate)
               VALUES (?,?,?,?,?,?)""",
            (eid, "시도", code, cid, votes, c.get("rate")),
        )
        n_res += 1

    con.commit()

    print(f"elections: {cur.execute('SELECT COUNT(*) FROM elections').fetchone()[0]}")
    print(f"candidates: {n_cand}  (당선자 {cur.execute('SELECT COUNT(*) FROM candidates WHERE is_elected=1').fetchone()[0]})")
    print(f"results(level=시도): {n_res}")
    print(f"정당 총수(자동등록 포함): {cur.execute('SELECT COUNT(*) FROM parties').fetchone()[0]}")
    print("회차별 후보/당선 수:")
    for row in cur.execute(
        """SELECT election_id, COUNT(*),
                  SUM(CASE WHEN is_elected=1 THEN 1 ELSE 0 END)
           FROM candidates GROUP BY election_id ORDER BY election_id"""
    ):
        print(f"  {row[0]}회: 후보 {row[1]}, 당선 {row[2]}")
    con.close()


if __name__ == "__main__":
    main()
