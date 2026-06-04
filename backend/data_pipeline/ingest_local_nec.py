"""기초단체장 낙선자 보강: 선관위 OpenAPI(개표결과 type4)로 후보 전원·정확 득표 교체.

ingest_local(위키, 당선+2위)을 NEC 완전 데이터로 갱신. NEC가 매칭한 (회차,시군구)만
교체하고, 매칭 못한 통합-전 시군은 위키 데이터 유지(=ingest_local 다음에 실행).
실행: python backend/data_pipeline/ingest_local_nec.py   (3~8회 전부)
이후 precompute.py → ingest_assembly.py → ingest_superintendent.py 재실행 필요.
"""
import sqlite3
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from ingest_council import (  # noqa: E402
    match_sigungu, build_region_list, fetch_all, SIDO_FULL2SHORT, num, SID2HOE,
)
from ingest_local import resolve_party  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DB = ROOT / "backend" / "db" / "election.sqlite"
OFFICE = "기초단체장"
TYPE = 4  # 구·시·군의 장
SGIDS = ["20020613", "20060531", "20100602", "20140604", "20180613", "20220601"]
SIDO_CODE = {
    "서울": "11", "부산": "26", "대구": "27", "인천": "28", "광주": "29", "대전": "30",
    "울산": "31", "세종": "36", "경기": "41", "강원": "42", "충북": "43", "충남": "44",
    "전북": "45", "전남": "46", "경북": "47", "경남": "48", "제주": "50",
}


def replace_race(cur, office, eid, code, cands):
    """(회차,지역)의 해당 office 후보 전체 삭제 후 재삽입. cands=[(party,name,votes,elected,rate)]."""
    cur.execute(
        "DELETE FROM results WHERE election_id=? AND region_code=? AND candidate_id IN "
        "(SELECT id FROM candidates WHERE office=?)", (eid, code, office))
    cur.execute("DELETE FROM candidates WHERE office=? AND election_id=? AND region_code=?",
                (office, eid, code))
    level = "시도" if office == "광역단체장" else "구시군"
    for party, nm, votes, elected, rate in cands:
        pid = resolve_party(cur, party, eid)
        cur.execute(
            "INSERT INTO candidates(election_id,office,region_code,name,party_id,is_elected)"
            " VALUES (?,?,?,?,?,?)", (eid, office, code, nm, pid, elected))
        cid = cur.lastrowid
        cur.execute(
            "INSERT INTO results(election_id,level,region_code,candidate_id,votes,vote_rate)"
            " VALUES (?,?,?,?,?,?)", (eid, level, code, cid, votes, rate))


def row_cands(row, wset, sd, sgg):
    cands = []
    for n in range(1, 51):
        nm = row.get(f"hbj{n:02d}")
        if nm:
            cands.append((row.get(f"jd{n:02d}") or "무소속", nm, num(row.get(f"dugsu{n:02d}"))))
    valid = sum(v for _, _, v in cands) or 1
    return [(p, nm, v, 1 if (sd, sgg, nm) in wset else 0, round(v / valid * 100, 2))
            for p, nm, v in cands]


def ingest_metro(cur):
    """광역단체장(type3=시도지사) 후보 전원 보강. 시도 단위(SIDO_CODE)."""
    OFFICE_M = "광역단체장"
    tot_race = tot_cand = 0
    for sgId in SGIDS:
        hoe = SID2HOE[sgId]
        win = fetch_all("WinnerInfoInqireService2/getWinnerInfoInqire", sgId, 3)
        wset = {(w["sdName"], w["sggName"], w["name"]) for w in win}
        tally = fetch_all("VoteXmntckInfoInqireService2/getXmntckSttusInfoInqire", sgId, 3)
        seen = set()
        nrace = 0
        for row in tally:
            if row.get("wiwName") != "합계":
                continue
            sd = row["sdName"]
            if sd not in SIDO_FULL2SHORT or sd in seen:
                continue
            seen.add(sd)
            code = SIDO_CODE[SIDO_FULL2SHORT[sd]]
            cands = row_cands(row, wset, sd, row.get("sggName"))
            replace_race(cur, OFFICE_M, hoe, code, cands)
            tot_cand += len(cands)
            nrace += 1
        tot_race += nrace
        print(f"  {hoe}회 광역: 시도 {nrace} (당선인API {len(win)})")
    print(f"광역단체장 NEC 보강: 시도·회차 {tot_race} / 후보 {tot_cand}행")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "both"
    con = sqlite3.connect(DB)
    cur = con.cursor()
    if mode in ("both", "metro"):
        ingest_metro(cur)
        con.commit()
    if mode == "metro":
        con.close()
        return
    rlist = build_region_list(con)

    total_repl = total_cand = 0
    for sgId in SGIDS:
        hoe = SID2HOE[sgId]
        win = fetch_all("WinnerInfoInqireService2/getWinnerInfoInqire", sgId, TYPE)
        wset = {(w["sdName"], w["sggName"], w["name"]) for w in win}
        whint = {(w["sdName"], w["sggName"]): w.get("wiwName") for w in win if w.get("wiwName")}
        tally = fetch_all("VoteXmntckInfoInqireService2/getXmntckSttusInfoInqire", sgId, TYPE)

        # (eid, code) -> 후보 [(party,name,votes,elected)]
        races = {}
        seen = set()
        contested = set()
        for row in tally:
            if row.get("wiwName") != "합계":
                continue
            sd, sgg = row["sdName"], row["sggName"]
            if sd not in SIDO_FULL2SHORT or (sd, sgg) in seen:
                continue
            seen.add((sd, sgg))
            sido = SIDO_FULL2SHORT[sd]
            code, _ = match_sigungu(rlist, sido, sgg, whint.get((sd, sgg)))
            if not code:
                continue
            contested.add((sd, sgg))
            cands = []
            for n in range(1, 51):
                nm = row.get(f"hbj{n:02d}")
                if nm:
                    cands.append((row.get(f"jd{n:02d}") or "무소속", nm, num(row.get(f"dugsu{n:02d}"))))
            valid = sum(v for _, _, v in cands) or 1
            races[(hoe, code)] = [
                (p, nm, v, 1 if (sd, sgg, nm) in wset else 0, round(v / valid * 100, 2))
                for p, nm, v in cands
            ]
        # 무투표 단체장 보강
        for w in win:
            sd, sgg = w["sdName"], w["sggName"]
            if (sd, sgg) in contested or sd not in SIDO_FULL2SHORT:
                continue
            sido = SIDO_FULL2SHORT[sd]
            code, _ = match_sigungu(rlist, sido, sgg, w.get("wiwName"))
            if not code:
                continue
            races.setdefault((hoe, code), []).append(
                (w.get("jdName") or "무소속", w["name"], None, 1, None))

        # race별 교체(매칭된 것만)
        for (eid, code), cands in races.items():
            cur.execute(
                "DELETE FROM results WHERE election_id=? AND region_code=? AND candidate_id IN "
                "(SELECT id FROM candidates WHERE office=?)", (eid, code, OFFICE))
            cur.execute("DELETE FROM candidates WHERE office=? AND election_id=? AND region_code=?",
                        (OFFICE, eid, code))
            for party, nm, votes, elected, rate in cands:
                pid = resolve_party(cur, party, eid)
                cur.execute(
                    "INSERT INTO candidates(election_id,office,region_code,name,party_id,is_elected)"
                    " VALUES (?,?,?,?,?,?)", (eid, OFFICE, code, nm, pid, elected))
                cid = cur.lastrowid
                cur.execute(
                    "INSERT INTO results(election_id,level,region_code,candidate_id,votes,vote_rate)"
                    " VALUES (?,?,?,?,?,?)", (eid, "구시군", code, cid, votes, rate))
                total_cand += 1
        total_repl += len(races)
        print(f"  {hoe}회: 시군구 교체 {len(races)} (당선인API {len(win)})")

    con.commit()
    print(f"기초단체장 NEC 보강: 시군구·회차 {total_repl} / 후보 {total_cand}행")
    n_win = cur.execute(
        "SELECT COUNT(*) FROM candidates WHERE office=? AND is_elected=1", (OFFICE,)).fetchone()[0]
    n_cand = cur.execute("SELECT COUNT(*) FROM candidates WHERE office=?", (OFFICE,)).fetchone()[0]
    print(f"기초단체장 전체: 후보 {n_cand} / 당선 {n_win}")
    con.close()


if __name__ == "__main__":
    main()
