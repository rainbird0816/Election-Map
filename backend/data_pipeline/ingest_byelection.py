"""재·보궐선거(보궐선거) 개표결과 적재.

선관위 OpenAPI 는 전국동시선거(대선/총선/지선)뿐 아니라
- 순수 재·보궐선거(상·하반기, 2010~)
- 정규선거일에 함께 치른 동시 보궐(예: 총선일의 시도지사 보궐, 대선일의 국회의원 보궐)
도 동일 구조로 제공한다.

이 스크립트는 CommonCodeService 로 전체 선거 코드를 받아
"보궐선거에 해당하는 (선거일, 직종)"만 자동 분류한 뒤, 각 직종을
개표결과(getXmntckSttusInfoInqire) + 당선인(getWinnerInfoInqire) 으로
선거구별 후보 전원(낙선 포함)·득표·당선 여부를 적재한다.

표현은 산발적 소수 선거구라 지도가 아닌 목록(선거일→직종→선거구→후보) 드릴다운.

실행: python backend/data_pipeline/ingest_byelection.py
키: backend/.secrets/nec_key.txt
"""
import sqlite3
import pathlib
import warnings

import httpx

warnings.filterwarnings("ignore")
ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DB = ROOT / "backend" / "db" / "election.sqlite"
KEY = (ROOT / "backend" / ".secrets" / "nec_key.txt").read_text(encoding="utf-8").strip()
BASE = "http://apis.data.go.kr/9760000"

# 직종코드 -> 이름
TYPE_NAME = {
    1: "대통령", 2: "국회의원", 3: "시도지사", 4: "구시군의장",
    5: "시도의원", 6: "구시군의원", 11: "교육감",
}
# 비례대표(7 국회/8 광역/9 기초/10 교육의원)는 보궐 대상이 아님 → 제외
PROP_TYPES = {"7", "8", "9", "10"}

# 시도지사 등 시도단위 집계행을 거르고 부모 시도명을 얻기 위한 맵(ingest_council 과 동일)
SIDO_FULL2SHORT = {
    "서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구", "인천광역시": "인천",
    "광주광역시": "광주", "대전광역시": "대전", "울산광역시": "울산", "세종특별자치시": "세종",
    "부산직할시": "부산", "대구직할시": "대구", "인천직할시": "인천", "광주직할시": "광주", "대전직할시": "대전",
    "경기도": "경기", "강원도": "강원", "강원특별자치도": "강원", "충청북도": "충북",
    "충청남도": "충남", "전라북도": "전북", "전북특별자치도": "전북", "전라남도": "전남",
    "경상북도": "경북", "경상남도": "경남", "제주특별자치도": "제주", "제주도": "제주",
}

cli = httpx.Client(timeout=60, verify=False)


def num(v):
    try:
        return int(str(v).replace(",", ""))
    except (ValueError, TypeError):
        return 0


def fetch_all(op, sgId, tc):
    """numOfRows 최대 100. totalCount 까지 페이지 루프."""
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


def code_table():
    """{sgId: {typecode(str): sgName}} 전체 선거 코드."""
    allit = []
    pg = 1
    while True:
        r = cli.get(f"{BASE}/CommonCodeService/getCommonSgCodeList", params={
            "serviceKey": KEY, "pageNo": pg, "numOfRows": 100, "resultType": "json"})
        body = r.json()["response"].get("body") or {}
        it = (body.get("items") or {}).get("item") or []
        if isinstance(it, dict):
            it = [it]
        allit += it
        total = int(body.get("totalCount") or 0)
        if not it or len(allit) >= total:
            break
        pg += 1
    byid = {}
    for x in allit:
        byid.setdefault(x["sgId"], {})[x["sgTypecode"]] = x["sgName"]
    return byid


def classify(byid):
    """보궐선거에 해당하는 [(sgId, sgtype:int, header, kind)] 산출.
    kind: '재보궐'(순수 재·보궐선거일) | '동시'(정규선거일 동시 보궐).
    정규선거의 본 직종은 제외하고, 그 외 직종을 보궐로 본다."""
    jobs = []
    for sg, types in sorted(byid.items()):
        hdr = types.get("0", "")
        present = [t for t in types if t != "0" and t not in PROP_TYPES]
        if "보궐" in hdr:
            main, kind = set(), "재보궐"
        elif "대통령선거" in hdr:
            main, kind = {"1"}, "동시"
        elif "국회의원선거" in hdr:
            main, kind = {"2"}, "동시"
        elif "전국동시지방선거" in hdr:
            main, kind = {"3", "4", "5", "6", "11"}, "동시"
        else:
            main, kind = set(), "재보궐"
        for t in present:
            if t in main:
                continue
            if int(t) not in TYPE_NAME:
                continue
            jobs.append((sg, int(t), hdr, kind))
    return jobs


def fmt_date(sg):
    return f"{sg[0:4]}-{sg[4:6]}-{sg[6:8]}"


def main():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.executescript("""
    DROP TABLE IF EXISTS byelection;
    CREATE TABLE byelection(
      sg_id TEXT, vote_date TEXT, label TEXT, kind TEXT,
      sgtype INT, sgtype_name TEXT,
      sido TEXT, sgg TEXT, region TEXT,
      idx INT, party TEXT, name TEXT, votes INT, rate REAL, elected INT);
    CREATE INDEX idx_bye ON byelection(sg_id, sgtype);
    """)

    byid = code_table()
    jobs = classify(byid)
    print(f"보궐 작업목록 {len(jobs)}건")

    nrows = nwin = nraces = 0
    for sg, tc, hdr, kind in jobs:
        label = hdr if kind == "재보궐" else f"{hdr} 동시보궐"
        vd = fmt_date(sg)
        win = fetch_all("WinnerInfoInqireService2/getWinnerInfoInqire", sg, tc)
        tally = fetch_all("VoteXmntckInfoInqireService2/getXmntckSttusInfoInqire", sg, tc)
        if not win and not tally:
            continue  # 미공개(예: 9회 지선 동시 국회의원 보궐)
        wset = {(w.get("sdName"), w.get("sggName"), w.get("name")) for w in win}
        # 선거구 -> 부모 구시군(wiwName) 힌트(시도의원/구시군의원 등 표시용)
        whint = {(w.get("sdName"), w.get("sggName")): w.get("wiwName") for w in win if w.get("wiwName")}

        contested = set()
        seen = set()
        jraces = jrows = jwin = 0
        for row in tally:
            if row.get("wiwName") != "합계":
                continue
            sd, sgg = row.get("sdName"), row.get("sggName")
            if sd not in SIDO_FULL2SHORT:
                continue  # sdName='합계' 등 전국 집계행 제외
            if (sd, sgg) in seen:
                continue  # crOrder 1/2 중복 합계행 제거
            seen.add((sd, sgg))
            contested.add((sd, sgg))
            sido = SIDO_FULL2SHORT.get(sd, sd)
            region = whint.get((sd, sgg)) or ""
            cands = []
            for n in range(1, 51):
                nm = row.get(f"hbj{n:02d}")
                if nm:
                    cands.append((row.get(f"jd{n:02d}") or "무소속", nm, num(row.get(f"dugsu{n:02d}"))))
            valid = sum(v for _, _, v in cands) or 1
            jraces += 1
            for i, (party, nm, v) in enumerate(cands):
                elected = 1 if (sd, sgg, nm) in wset else 0
                jwin += elected
                cur.execute("INSERT INTO byelection VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (sg, vd, label, kind, tc, TYPE_NAME[tc], sido, sgg, region,
                             i, party, nm, v, round(v / valid * 100, 2), elected))
                jrows += 1
        # 무투표당선(개표결과에 없는 선거구의 당선인) 보강
        for w in win:
            sd, sgg = w.get("sdName"), w.get("sggName")
            if (sd, sgg) in contested:
                continue
            sido = SIDO_FULL2SHORT.get(sd, sd)
            cur.execute("INSERT INTO byelection VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (sg, vd, label, kind, tc, TYPE_NAME[tc], sido, sgg, w.get("wiwName") or "",
                         0, w.get("jdName") or "무소속", w.get("name"), None, None, 1))
            jraces += 1
            jrows += 1
            jwin += 1
        nrows += jrows
        nwin += jwin
        nraces += jraces
        print(f"  {sg} {kind:3} {TYPE_NAME[tc]:6}: 선거구 {jraces:3} 후보 {jrows:4} 당선 {jwin:3} / 당선인API {len(win)}")

    con.commit()
    tot = cur.execute("SELECT COUNT(*) FROM byelection").fetchone()[0]
    elc = cur.execute("SELECT COUNT(*) FROM byelection WHERE elected=1").fetchone()[0]
    ndate = cur.execute("SELECT COUNT(DISTINCT sg_id) FROM byelection").fetchone()[0]
    print(f"\n적재 완료: 선거일 {ndate} · 선거구 {nraces} · 후보 {tot}행 · 당선 {elc}명")
    con.close()


if __name__ == "__main__":
    main()
