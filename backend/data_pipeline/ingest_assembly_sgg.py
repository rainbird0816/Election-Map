"""총선(국회의원) 선거구별 후보(낙선+당선) 적재 — 선관위 OpenAPI(개표 type2).

14~22대(1992~2024). 13대는 OpenAPI 미제공(시도집계만). 선거구 단위(시도→선거구 드릴다운용).
실행: python backend/data_pipeline/ingest_assembly_sgg.py [대수]   (기본 전부)
"""
import sqlite3
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from ingest_council import fetch_all, SIDO_FULL2SHORT, num  # noqa: E402

DB = pathlib.Path(__file__).resolve().parent.parent / "db" / "election.sqlite"
# 대수 -> sgId (본선거만; 재보궐 제외)
SGID = {14: "19920324", 15: "19960411", 16: "20000413", 17: "20040415", 18: "20080409",
        19: "20120411", 20: "20160413", 21: "20200415", 22: "20240410"}


def main():
    targets = [int(sys.argv[1])] if len(sys.argv) > 1 else list(SGID)
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS assembly_sgg(
      daesu INT, sido TEXT, sgg TEXT, idx INT, party TEXT, name TEXT,
      votes INT, rate REAL, elected INT);
    CREATE INDEX IF NOT EXISTS idx_asgg ON assembly_sgg(daesu, sido);
    """)
    for daesu in targets:
        sgId = SGID[daesu]
        cur.execute("DELETE FROM assembly_sgg WHERE daesu=?", (daesu,))
        win = fetch_all("WinnerInfoInqireService2/getWinnerInfoInqire", sgId, 2)
        wset = {(w["sdName"], w["sggName"], w["name"]) for w in win}
        tally = fetch_all("VoteXmntckInfoInqireService2/getXmntckSttusInfoInqire", sgId, 2)
        seen, contested, nseats = set(), set(), 0
        for row in tally:
            if row.get("wiwName") != "합계":
                continue
            sd, sgg = row["sdName"], row["sggName"]
            if sd not in SIDO_FULL2SHORT or (sd, sgg) in seen:
                continue
            seen.add((sd, sgg)); contested.add((sd, sgg))
            sido = SIDO_FULL2SHORT[sd]
            cands = []
            for n in range(1, 51):
                nm = row.get(f"hbj{n:02d}")
                if nm:
                    cands.append((row.get(f"jd{n:02d}") or "무소속", nm, num(row.get(f"dugsu{n:02d}"))))
            valid = sum(v for _, _, v in cands) or 1
            for i, (party, nm, v) in enumerate(cands):
                el = 1 if (sd, sgg, nm) in wset else 0
                nseats += el
                cur.execute("INSERT INTO assembly_sgg VALUES(?,?,?,?,?,?,?,?,?)",
                            (daesu, sido, sgg, i, party, nm, v, round(v / valid * 100, 2), el))
        # 무투표당선 보강
        nbye = 0
        for w in win:
            sd, sgg = w["sdName"], w["sggName"]
            if (sd, sgg) in contested or sd not in SIDO_FULL2SHORT:
                continue
            cur.execute("INSERT INTO assembly_sgg VALUES(?,?,?,?,?,?,?,?,?)",
                        (daesu, SIDO_FULL2SHORT[sd], sgg, nbye, w.get("jdName") or "무소속",
                         w["name"], None, None, 1))
            nbye += 1
        con.commit()
        print(f"{daesu}대({sgId}): 선거구 {len(contested)} / 당선 {nseats}+무투표 {nbye}={nseats + nbye} / 당선인API {len(win)}")
    con.close()


if __name__ == "__main__":
    main()
