"""기초단체장(구청장/시장/군수) 개표결과(data/raw/local_mayors.json) -> SQLite.

시군구명 -> 코드는 regions 테이블(seed_sigungu로 적재됨)에서 시도 범위 안에서 해소.
당선자 = (회차, 시군구)별 최고 득표율.
선행: init_db.py, seed_sigungu.py, ingest.py(정당 시드 존재) 실행.
실행: python backend/data_pipeline/ingest_local.py
"""
import json
import sqlite3
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DB = ROOT / "backend" / "db" / "election.sqlite"
RAW = ROOT / "data" / "raw" / "local_mayors.json"
OFFICE = "기초단체장"

# 시도명 -> 행정표준 시도 코드 (regions 시도 parent와 매칭)
SIDO_CODE = {
    "서울": "11", "부산": "26", "대구": "27", "인천": "28", "광주": "29",
    "대전": "30", "울산": "31", "세종": "36", "경기": "41", "강원": "42",
    "충북": "43", "충남": "44", "전북": "45", "전남": "46", "경북": "47",
    "경남": "48", "제주": "50",
}

# ingest.py 와 동일한 정당 매핑/색상 (재사용)
SEEDED = {
    "새천년민주당": 11, "열린우리당": 12, "새정치민주연합": 17, "더불어민주당": 18,
    "한나라당": 21, "새누리당": 22, "자유한국당": 23, "미래통합당": 24, "국민의힘": 25,
    "민주노동당": 31, "통합진보당": 32, "정의당": 33,
    "자유민주연합": 41, "자유선진당": 42, "국민의당": 51, "바른미래당": 52,
    "무소속": 61,
}
MINOR_COLORS = {
    "국민중심당": "#006666", "진보신당": "#D7003A", "국민참여당": "#F58220",
    "노동당": "#E5007F", "민주평화당": "#00B5A5", "민중당": "#E50000",
    "녹색당": "#00A651", "기본소득당": "#00D2C6", "진보당": "#D6001C",
    "창조한국당": "#FFA500", "친박연합": "#B0306B",
}

# 시군구 개명 등 별칭: (시도 행정표준코드, 문서표기명) -> 지오/DB 등록명
SIGUNGU_ALIAS = {
    ("28", "미추홀구"): "남구",  # 인천 남구 -> 2018 미추홀구 (지오파일은 남구)
    ("41", "여주군"): "여주시",   # 경기 여주군 -> 2013 여주시 승격 (지오파일은 여주시)
    ("44", "당진군"): "당진시",   # 충남 당진군 -> 2012 당진시 승격 (지오파일은 당진시)
    ("41", "양주군"): "양주시",   # 경기 양주군 -> 2003 양주시 승격
    ("41", "포천군"): "포천시",   # 경기 포천군 -> 2003 포천시 승격
}


def resolve_party(cur, name, hoecha):
    if name == "민주당":
        return 10 if hoecha == 4 else 15
    if name in SEEDED:
        return SEEDED[name]
    row = cur.execute("SELECT id FROM parties WHERE name=?", (name,)).fetchone()
    if row:
        return row[0]
    cur.execute(
        "INSERT INTO parties(name,lineage_id,color_hex) VALUES (?,7,?)",
        (name, MINOR_COLORS.get(name, "#9E9E9E")),
    )
    return cur.lastrowid


def build_name_to_code(cur):
    """{(시도코드, 시군구명): 시군구코드} — regions에서 구성."""
    out = {}
    for code, name, parent in cur.execute(
        "SELECT code, name, parent_code FROM regions WHERE level='시군구'"
    ):
        out[(parent, name)] = code
    return out


def main():
    data = json.loads(RAW.read_text(encoding="utf-8"))
    con = sqlite3.connect(DB)
    cur = con.cursor()
    name2code = build_name_to_code(cur)

    # 멱등성: 기존 기초단체장 적재분 제거
    cur.execute(
        """DELETE FROM results WHERE candidate_id IN
           (SELECT id FROM candidates WHERE office=?)""", (OFFICE,))
    cur.execute("DELETE FROM candidates WHERE office=?", (OFFICE,))

    # (회차, 시군구코드)별 최고 득표율 -> 당선자
    best = {}
    rows_resolved = []
    misses = set()
    for c in data["candidates"]:
        sido = SIDO_CODE[c["sido"]]
        gu = SIGUNGU_ALIAS.get((sido, c["sigungu"]), c["sigungu"])
        code = name2code.get((sido, gu))
        if not code:
            misses.add((c["sido"], c["sigungu"]))
            continue
        rate = c.get("rate") or 0
        key = (c["hoecha"], code)
        if key not in best or rate > best[key]:
            best[key] = rate
        rows_resolved.append((c, code))

    if misses:
        print("WARN 미해소 시군구:", sorted(misses))

    n_cand = 0
    for c, code in rows_resolved:
        eid = c["hoecha"]
        pid = resolve_party(cur, c["party"], eid)
        rate = c.get("rate")
        is_elected = 1 if (rate or 0) == best[(eid, code)] else 0
        cur.execute(
            """INSERT INTO candidates(election_id,office,region_code,name,party_id,is_elected)
               VALUES (?,?,?,?,?,?)""",
            (eid, OFFICE, code, c["name"], pid, is_elected),
        )
        cid = cur.lastrowid
        cur.execute(
            """INSERT INTO results(election_id,level,region_code,candidate_id,votes,vote_rate)
               VALUES (?,?,?,?,?,?)""",
            (eid, "구시군", code, cid, c.get("votes"), rate),
        )
        n_cand += 1

    con.commit()
    n_win = cur.execute(
        "SELECT COUNT(*) FROM candidates WHERE office=? AND is_elected=1", (OFFICE,)
    ).fetchone()[0]
    print(f"기초단체장 후보: {n_cand} (당선 {n_win})")
    for row in cur.execute(
        """SELECT election_id, COUNT(*) FROM candidates WHERE office=?
           GROUP BY election_id ORDER BY election_id""", (OFFICE,)):
        print(f"  {row[0]}회: 후보 {row[1]}")
    con.close()


if __name__ == "__main__":
    main()
