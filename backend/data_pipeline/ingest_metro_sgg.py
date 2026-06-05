"""시군구별 광역단체장(시도지사 type3)·광역비례(시도의원 비례 type8) 개표결과 적재 -> metro_sgg.

기존 region_election_summary/results/council 과 충돌하지 않도록 별도 테이블에 격리한다.
("광역 종합" 탭: 광역 클릭 시 기초별 도지사 1위 색칠, 기초 클릭 시 도지사·광역비례 득표 패널)

NEC VoteXmntckInfoInqireService2 의 시군구 행(wiwName != '합계')에 hbj/jd/dugsu(후보/정당/득표)가 들어있다.
세종 등 일부와 일반구(수원시장안구 등)는 match_sigungu(wiwName 힌트)로 시 단위 region 코드에 합산.
실행: python backend/data_pipeline/ingest_metro_sgg.py [sgId]   (기본 3~8회 전부)
키: backend/.secrets/nec_key.txt
"""
import sqlite3
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from ingest_council import (  # noqa: E402
    fetch_all, SIDO_FULL2SHORT, match_sigungu, build_region_list, SID2HOE, num,
)

DB = pathlib.Path(__file__).resolve().parent.parent / "db" / "election.sqlite"
SGIDS = ["20020613", "20060531", "20100602", "20140604", "20180613", "20220601"]
TALLY = "VoteXmntckInfoInqireService2/getXmntckSttusInfoInqire"


def ingest_office(cur, rlist, sgId, hoe, tc, office, has_cand):
    """type tc 개표 tally를 시군구별로 합산해 metro_sgg 적재.
    has_cand=True 면 후보명(hbj) 보존(도지사), False 면 정당 득표만(광역비례)."""
    tally = fetch_all(TALLY, sgId, tc)
    # agg[sgcode] = {"name": 시군구명, "rows": {key: [party, name, votes]}}
    agg = {}
    seen = set()
    nmiss = 0
    for row in tally:
        wiw = row.get("wiwName")
        if not wiw or wiw == "합계":
            continue
        sd = row.get("sdName")
        if sd not in SIDO_FULL2SHORT:
            continue  # 'sdName=합계' 등 상위 집계행 제외
        if (sd, wiw) in seen:
            continue
        seen.add((sd, wiw))
        sido = SIDO_FULL2SHORT[sd]
        sgcode, sgname = match_sigungu(rlist, sido, row.get("sggName") or "", wiw)
        if not sgcode:
            nmiss += 1
            continue
        bucket = agg.setdefault(sgcode, {"name": sgname, "sido": sido, "rows": {}})
        for n in range(1, 51):
            party = row.get(f"jd{n:02d}")
            if not party:
                continue
            name = row.get(f"hbj{n:02d}") or None
            if has_cand and not name:
                continue
            votes = num(row.get(f"dugsu{n:02d}"))
            key = (party, name) if has_cand else (party,)
            rec = bucket["rows"].setdefault(key, [party, name, 0])
            rec[2] += votes

    ninsert = 0
    for sgcode, b in agg.items():
        valid = sum(r[2] for r in b["rows"].values()) or 1
        for (party, name, votes) in b["rows"].values():
            cur.execute(
                "INSERT INTO metro_sgg(hoecha,office,sido,sigungu_code,sigungu_name,party,name,votes,rate)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (hoe, office, b["sido"], sgcode, b["name"], party, name, votes,
                 round(votes / valid * 100, 2)))
            ninsert += 1
    print(f"  {hoe}회 {office}: 시군구 {len(agg)} / 행 {ninsert} / 미매칭 {nmiss}")


def main():
    targets = [sys.argv[1]] if len(sys.argv) > 1 else SGIDS
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS metro_sgg(
      hoecha INT, office TEXT, sido TEXT, sigungu_code TEXT, sigungu_name TEXT,
      party TEXT, name TEXT, votes INT, rate REAL);
    CREATE INDEX IF NOT EXISTS idx_metro_sgg ON metro_sgg(hoecha, sigungu_code, office);
    """)
    for sgId in targets:
        hoe = SID2HOE[sgId]
        cur.execute("DELETE FROM metro_sgg WHERE hoecha=?", (hoe,))
        ingest_office(cur, build_region_list(con), sgId, hoe, 3, "광역단체장", True)
        ingest_office(cur, build_region_list(con), sgId, hoe, 8, "광역비례", False)
        con.commit()
    tot = cur.execute("SELECT office, COUNT(*) FROM metro_sgg GROUP BY office").fetchall()
    print("metro_sgg 합계:", dict(tot))
    con.close()


if __name__ == "__main__":
    main()
