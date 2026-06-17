"""지방의원(광역의원=시도의원 type5, 기초의원=구시군의원 type6) 개표결과 적재.

선관위 OpenAPI(VoteXmntckInfoInqireService2.getXmntckSttusInfoInqire) =
선거구별 후보 전원(낙선 포함) 득표. 당선 여부는 WinnerInfoInqireService2 로 보강.
선거구명(sggName) 접두로 부모 시군구 region 매칭.
실행: python backend/data_pipeline/ingest_council.py [sgId]  (기본 20220601=8회)
키: backend/.secrets/nec_key.txt
"""
import re
import sqlite3
import pathlib
import sys
import warnings

import httpx

warnings.filterwarnings("ignore")
ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DB = ROOT / "backend" / "db" / "election.sqlite"
KEY = (ROOT / "backend" / ".secrets" / "nec_key.txt").read_text(encoding="utf-8").strip()
BASE = "http://apis.data.go.kr/9760000"

SID2HOE = {"20020613": 3, "20060531": 4, "20100602": 5, "20140604": 6, "20180613": 7,
           "20220601": 8, "20260603": 9}  # 9회(2026): 선관위 OpenAPI 공개 후 적재 가능
SIDO_FULL2SHORT = {
    "서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구", "인천광역시": "인천",
    "광주광역시": "광주", "대전광역시": "대전", "울산광역시": "울산", "세종특별자치시": "세종",
    "부산직할시": "부산", "대구직할시": "대구", "인천직할시": "인천", "광주직할시": "광주", "대전직할시": "대전",
    "경기도": "경기", "강원도": "강원", "강원특별자치도": "강원", "충청북도": "충북",
    "충청남도": "충남", "전라북도": "전북", "전북특별자치도": "전북", "전라남도": "전남",
    "경상북도": "경북", "경상남도": "경남", "제주특별자치도": "제주", "제주도": "제주",
}
SIDO_CODE = {
    "서울": "11", "부산": "26", "대구": "27", "인천": "28", "광주": "29", "대전": "30",
    "울산": "31", "세종": "36", "경기": "41", "강원": "42", "충북": "43", "충남": "44",
    "전북": "45", "전남": "46", "경북": "47", "경남": "48", "제주": "50",
}
TYPES = {5: "광역의원", 6: "기초의원"}

cli = httpx.Client(timeout=60, verify=False)


def fetch_all(op, sgId, tc):
    """이 API는 numOfRows 최대 100. totalCount 까지 페이지 루프."""
    rows, pg = [], 1
    while True:
        r = cli.get(f"{BASE}/{op}", params={
            "serviceKey": KEY, "pageNo": pg, "numOfRows": 100,
            "sgId": sgId, "sgTypecode": str(tc), "resultType": "json"})
        body = r.json()["response"].get("body") or {}
        items = (body.get("items") or {}).get("item") or []
        if isinstance(items, dict):
            items = [items]
        rows += items
        total = int(body.get("totalCount") or 0)
        if not items or len(rows) >= total:
            break
        pg += 1
    return rows


def num(v):
    try:
        return int(str(v).replace(",", ""))
    except (ValueError, TypeError):
        return 0


_SUFFIX = [re.compile(r"제\d+선거구$"),
           re.compile(r"[가나다라마바사아자차카타파하]선거구$"),
           re.compile(r"선거구$")]


def parse_sigungu(sgg):
    """선거구명 -> 부모 시군구명. '종로구제1선거구'->종로구, '의령군선거구'->의령군,
    '수원시장안구가선거구'->수원시장안구, '수원시제1선거구'->수원시."""
    for pat in _SUFFIX:
        m = pat.search(sgg)
        if m:
            return sgg[:m.start()]
    return sgg


# 선거구명 표기 → DB region 명 별칭(개명/승격/통합/단층)
ALIAS = {
    "미추홀구": "남구", "세종특별자치시": "세종시",
    "여주군": "여주시", "당진군": "당진시", "양주군": "양주시", "포천군": "포천시",
    "남제주군": "서귀포시", "북제주군": "제주시",
    # 제주도의회 광역의원(4~6회)은 도 전역 번호선거구 → 제주시에 일괄 표시
    "제주도": "제주시", "제주특별자치도": "제주시",
    # 1·2회(1995·1998) 당시 군 → 이후 시 승격
    "광주군": "광주시", "김포군": "김포시", "안성군": "안성시", "용인군": "용인시",
    "이천군": "이천시", "파주군": "파주시", "화성군": "화성시", "양산군": "양산시",
    "논산군": "논산시",
    # 1998 여수시+여천시+여천군 통합 → 여수시
    "여천군": "여수시", "여천시": "여수시",
}


def build_region_list(con):
    """{sido_short: [(name, code)]} 이름 길이 내림차순(부분일치용)."""
    idx = {}
    for code, name, parent in con.execute(
            "SELECT code, name, parent_code FROM regions WHERE LENGTH(code)>2"):
        sido = next((s for s, c in SIDO_CODE.items() if parent == c), None)
        if sido:
            idx.setdefault(sido, []).append((name, code))
    # 2023.7 군위군(37310, regions상 경북 소속) 대구 편입. 편입 이후 자료(9회 등)는
    # 군위를 '대구' 키로 보내므로 '대구' 버킷에도 등록(코드는 37310 유지, 경북 버킷도 유지
    # → 8회 이전 경북 자료 매칭엔 영향 없음).
    gunwi = next(((n, c) for n, c in idx.get("경북", []) if c == "37310"), None)
    if gunwi and gunwi not in idx.get("대구", []):
        idx.setdefault("대구", []).append(gunwi)
    for s in idx:
        idx[s].sort(key=lambda x: -len(x[0]))
    return idx


def match_sigungu(rlist, sido, sgg, hint=None):
    """선거구명->부모 시군구 region: 파싱명->부분일치->당선인 wiwName(구시군) 힌트 순.
    hint는 2002 기초의원(동명 선거구)처럼 선거구명에 구가 없을 때 사용."""
    cand = parse_sigungu(sgg)
    cand = ALIAS.get(cand, cand)
    lst = rlist.get(sido, [])
    for name, code in lst:
        if name == cand:
            return code, cand
    for name, code in lst:
        if name in sgg:
            return code, name
    if hint:
        h = re.sub(r"\([^)]*\)\s*$", "", hint).strip()  # '중구(대구)'->'중구'
        h = ALIAS.get(h, h)
        for name, code in lst:
            if name == h:
                return code, name
        for name, code in lst:  # 일반구 '수원시권선구'->'수원시'
            if name in h:
                return code, name
    return None, cand


def main():
    sgId = sys.argv[1] if len(sys.argv) > 1 else "20220601"
    hoe = SID2HOE.get(sgId, 0)
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS council(
      hoecha INT, sgtype INT, sido TEXT, sigungu_code TEXT, sigungu_name TEXT,
      sgg TEXT, idx INT, party TEXT, name TEXT, votes INT, rate REAL, elected INT);
    CREATE INDEX IF NOT EXISTS idx_council ON council(hoecha, sigungu_code, sgtype);
    """)
    cur.execute("DELETE FROM council WHERE hoecha=?", (hoe,))
    rlist = build_region_list(con)

    for tc in TYPES:
        win = fetch_all("WinnerInfoInqireService2/getWinnerInfoInqire", sgId, tc)
        wset = {(w["sdName"], w["sggName"], w["name"]) for w in win}
        whint = {(w["sdName"], w["sggName"]): w.get("wiwName") for w in win if w.get("wiwName")}
        tally = fetch_all("VoteXmntckInfoInqireService2/getXmntckSttusInfoInqire", sgId, tc)
        nseats = nmiss = 0
        seen_sgg = set()  # (sdName, sgg) 중복 합계행(crOrder 1/2) 제거
        contested = set()
        for row in tally:
            if row.get("wiwName") != "합계":
                continue
            sd, sgg = row["sdName"], row["sggName"]
            if sd not in SIDO_FULL2SHORT:
                continue  # sdName='합계' 등 시도 집계행 제외
            if (sd, sgg) in seen_sgg:
                continue
            seen_sgg.add((sd, sgg))
            contested.add((sd, sgg))
            sido = SIDO_FULL2SHORT.get(sd, sd)
            sgcode, sgname = match_sigungu(rlist, sido, sgg, whint.get((sd, sgg)))
            if not sgcode:
                nmiss += 1
            cands = []
            for n in range(1, 51):
                nm = row.get(f"hbj{n:02d}")
                if nm:
                    cands.append((row.get(f"jd{n:02d}") or "무소속", nm, num(row.get(f"dugsu{n:02d}"))))
            valid = sum(v for _, _, v in cands) or 1
            for i, (party, nm, v) in enumerate(cands):
                elected = 1 if (sd, sgg, nm) in wset else 0
                cur.execute("INSERT INTO council VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                            (hoe, tc, sido, sgcode, sgname, sgg, i, party, nm, v,
                             round(v / valid * 100, 2), elected))
                nseats += elected
        # 무투표당선(개표결과에 없는 선거구의 당선인 전원) 보강
        nbye = 0
        for w in win:
            sd, sgg = w["sdName"], w["sggName"]
            if (sd, sgg) in contested:
                continue
            sido = SIDO_FULL2SHORT.get(sd, sd)
            sgcode, sgname = match_sigungu(rlist, sido, sgg, w.get("wiwName"))
            if not sgcode:
                nmiss += 1
            cur.execute("INSERT INTO council VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                        (hoe, tc, sido, sgcode, sgname, sgg, nbye, w.get("jdName") or "무소속",
                         w["name"], None, None, 1))
            nbye += 1
        print(f"  type{tc} {TYPES[tc]}: 선거구 {len(contested)} 당선 {nseats}+무투표 {nbye}={nseats + nbye} / 당선인API {len(win)} / 시군구미매칭행 {nmiss}")

    con.commit()
    tot = cur.execute("SELECT COUNT(*) FROM council WHERE hoecha=?", (hoe,)).fetchone()[0]
    elc = cur.execute("SELECT COUNT(*) FROM council WHERE hoecha=? AND elected=1", (hoe,)).fetchone()[0]
    print(f"{hoe}회 지방의원: 후보 {tot}행 / 당선 {elc}명")
    con.close()


if __name__ == "__main__":
    main()
