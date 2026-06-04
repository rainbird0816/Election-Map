"""지방의원 비례대표(광역비례 type8, 기초비례 type9) 당선자 적재 -> council(sgtype 8/9).

광역비례=시도 단위(sigungu_code NULL), 기초비례=시군구 단위. 당선자 명단+정당(의석).
council 테이블 재사용(sgg='비례대표'). sgtype 8/9만 갱신(5/6 지역구는 보존).
실행: python backend/data_pipeline/ingest_council_pr.py [sgId]   (기본 3~8회 전부)
"""
import sqlite3
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from ingest_council import (  # noqa: E402
    fetch_all, SIDO_FULL2SHORT, match_sigungu, build_region_list, SID2HOE,
)

DB = pathlib.Path(__file__).resolve().parent.parent / "db" / "election.sqlite"
SGIDS = ["20020613", "20060531", "20100602", "20140604", "20180613", "20220601"]


def main():
    targets = [sys.argv[1]] if len(sys.argv) > 1 else SGIDS
    con = sqlite3.connect(DB)
    cur = con.cursor()
    rlist = build_region_list(con)
    for sgId in targets:
        hoe = SID2HOE[sgId]
        cur.execute("DELETE FROM council WHERE hoecha=? AND sgtype IN (8,9)", (hoe,))
        cnt = {8: 0, 9: 0}
        for sgtype in (8, 9):
            win = fetch_all("WinnerInfoInqireService2/getWinnerInfoInqire", sgId, sgtype)
            for i, w in enumerate(win):
                sd = w["sdName"]
                if sd not in SIDO_FULL2SHORT:
                    continue
                sido = SIDO_FULL2SHORT[sd]
                code = None
                sgnm = None
                if sgtype == 9:
                    code, sgnm = match_sigungu(rlist, sido, w.get("sggName") or "", w.get("wiwName"))
                cur.execute("INSERT INTO council VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                            (hoe, sgtype, sido, code, sgnm, "비례대표", i,
                             w.get("jdName") or "무소속", w["name"], None, None, 1))
                cnt[sgtype] += 1
        con.commit()
        print(f"{hoe}회: 광역비례 {cnt[8]} / 기초비례 {cnt[9]}")
    con.close()


if __name__ == "__main__":
    main()
