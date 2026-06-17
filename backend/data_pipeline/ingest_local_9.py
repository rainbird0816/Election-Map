"""제9회(2026) 기초단체장(구·시·군의 장) 후보 전원 -> candidates/results 적재.

소스:
  data/raw/nec9_ec4.json       개표결과(후보 전원, 낙선 포함)
  data/raw/nec9_ec4_win.json   당선인 명부(무투표 포함, 당선 표시·무투표 보강용)

일반구 도시(수원/창원 등)는 개표표가 시 합계행 + 구별 분해행으로 나오는데,
parse_districts 가 분해행 후보명을 득표율로 오인하므로 시군구별 '첫 유효행(시 합계)'만 사용.
당선자는 명부와 대조해 is_elected=1. region_election_summary 는 precompute.py 가 재생성.
실행: python backend/data_pipeline/ingest_local_9.py  (이후 precompute.py)
"""
import json
import pathlib
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from ingest_council import build_region_list, match_sigungu  # noqa: E402
from ingest import resolve_party  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DB = ROOT / "backend" / "db" / "election.sqlite"
RAW = ROOT / "data" / "raw"
HOE = 9
OFFICE = "기초단체장"

STD2SHORT = {
    "11": "서울", "26": "부산", "27": "대구", "28": "인천", "29": "광주", "30": "대전",
    "31": "울산", "36": "세종", "41": "경기", "42": "강원", "43": "충북", "44": "충남",
    "45": "전북", "46": "전남", "47": "경북", "48": "경남", "50": "제주",
}


def _is_num(s):
    try:
        float(s)
        return True
    except (ValueError, TypeError):
        return False


def main():
    tally = json.loads((RAW / "nec9_ec4.json").read_text(encoding="utf-8"))["rows"]
    wins = json.loads((RAW / "nec9_ec4_win.json").read_text(encoding="utf-8"))["winners"]
    winset = {(w["sido_std"], w["sigungu"], w["name"]) for w in wins}

    # 시군구별 첫 유효행(후보명이 숫자가 아닌 = 시 합계행)만 채택
    seen = {}
    for r in tally:
        key = (r["sido_std"], r["sigungu"])
        if key in seen:
            continue
        if r["cands"] and not _is_num(r["cands"][0]["name"]):
            seen[key] = r

    con = sqlite3.connect(DB)
    cur = con.cursor()
    # 멱등성: 9회 기초단체장만 제거(광역단체장 9회 보존)
    cur.execute("DELETE FROM results WHERE election_id=? AND candidate_id IN "
                "(SELECT id FROM candidates WHERE election_id=? AND office=?)",
                (HOE, HOE, OFFICE))
    cur.execute("DELETE FROM candidates WHERE election_id=? AND office=?", (HOE, OFFICE))

    rlist = build_region_list(con)
    ncand = nwin = nmiss = 0
    miss = []
    for (std, sigungu), r in seen.items():
        short = STD2SHORT.get(std)
        sgcode, sgname = match_sigungu(rlist, short, sigungu, sigungu)
        if not sgcode:
            nmiss += 1
            miss.append((short, sigungu))
            continue
        for c in r["cands"]:
            elected = 1 if (std, sigungu, c["name"]) in winset else 0
            pid = resolve_party(cur, c["party"], HOE)
            cur.execute(
                "INSERT INTO candidates(election_id,office,region_code,name,party_id,is_elected)"
                " VALUES (?,?,?,?,?,?)",
                (HOE, OFFICE, sgcode, c["name"], pid, elected))
            cid = cur.lastrowid
            cur.execute(
                "INSERT INTO results(election_id,level,region_code,candidate_id,votes,vote_rate)"
                " VALUES (?,?,?,?,?,?)",
                (HOE, "구시군", sgcode, cid, c.get("votes"), c.get("rate")))
            ncand += 1
            nwin += elected

    # 무투표/개표누락 시군구: 명부 당선자만 추가
    for w in wins:
        if (w["sido_std"], w["sigungu"]) in seen:
            continue
        short = STD2SHORT.get(w["sido_std"])
        sgcode, sgname = match_sigungu(rlist, short, w["sigungu"], w["sigungu"])
        if not sgcode:
            nmiss += 1
            continue
        pid = resolve_party(cur, w["party"], HOE)
        cur.execute(
            "INSERT INTO candidates(election_id,office,region_code,name,party_id,is_elected)"
            " VALUES (?,?,?,?,?,1)",
            (HOE, OFFICE, sgcode, w["name"], pid))
        cid = cur.lastrowid
        cur.execute(
            "INSERT INTO results(election_id,level,region_code,candidate_id,votes,vote_rate)"
            " VALUES (?,?,?,?,?,?)",
            (HOE, "구시군", sgcode, cid, w.get("votes"), w.get("rate")))
        ncand += 1
        nwin += 1

    con.commit()
    nreg = cur.execute("SELECT COUNT(DISTINCT region_code) FROM candidates "
                       "WHERE election_id=? AND office=?", (HOE, OFFICE)).fetchone()[0]
    print(f"기초단체장 9회: 후보 {ncand} / 당선 {nwin} / 시군구 {nreg} / 미매칭 {nmiss}"
          + (f" {miss[:8]}" if miss else ""))
    print("→ precompute.py 실행해 region_election_summary 재생성 필요")
    con.close()


if __name__ == "__main__":
    main()
