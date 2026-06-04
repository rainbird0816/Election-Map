"""korea-election-map 백엔드 (FastAPI).
실행: uvicorn app.main:app --reload --port 8000  (backend/ 에서)
"""
import json
import sqlite3
import pathlib
from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

DB = pathlib.Path(__file__).resolve().parent.parent / "db" / "election.sqlite"
DIST = pathlib.Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

app = FastAPI(title="korea-election-map")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
api = APIRouter()


def q(sql, args=()):
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    try:
        rows = [dict(r) for r in con.execute(sql, args)]
    finally:
        con.close()
    return rows


@api.get("/health")
def health():
    return {"ok": True}


@api.get("/elections")
def elections():
    """선거 회차 목록 (회차 셀렉터용)."""
    return q("SELECT * FROM elections ORDER BY election_date")


@api.get("/map")
def map_data(election_id: int, office: str = "광역단체장", parent: str | None = None):
    """지역별 1위 정당색 -> 프론트 채색.
    parent 지정 시 해당 시도의 하위(시군구)만 반환(기초단체장 드릴다운)."""
    sql = """SELECT s.region_code, r.name AS region_name, r.parent_code,
                    s.winner_candidate_id, s.winner_party_id, s.winner_rate,
                    s.turnout, c.name AS winner_name, p.name AS party_name,
                    p.color_hex, s.top_parties_json
             FROM region_election_summary s
             JOIN parties p    ON p.id = s.winner_party_id
             LEFT JOIN candidates c ON c.id = s.winner_candidate_id
             LEFT JOIN regions r    ON r.code = s.region_code
             WHERE s.election_id = ? AND s.office = ?"""
    args = [election_id, office]
    if parent is not None:
        sql += " AND r.parent_code = ?"
        args.append(parent)
    return q(sql, tuple(args))


@api.get("/region/{code}/history")
def region_history(code: str, office: str = "광역단체장"):
    """지역 상세: 역대 당선자 + 역대 결과 추이."""
    winners = q(
        """SELECT e.id AS election_id, e.name, e.hoecha, e.election_date,
                  c.name AS cand, c.party_id, p.name AS party_name, p.color_hex
           FROM elected_seats s
           JOIN elections e   ON e.id = s.election_id
           JOIN candidates c  ON c.id = s.candidate_id
           LEFT JOIN parties p ON p.id = c.party_id
           WHERE s.region_code = ? AND s.office = ?
           ORDER BY e.election_date""",
        (code, office),
    )
    trend = q(
        """SELECT s.election_id, e.hoecha, e.election_date,
                  s.winner_party_id, p.name AS party_name, p.color_hex,
                  s.winner_rate, s.turnout, s.top_parties_json
           FROM region_election_summary s
           JOIN elections e    ON e.id = s.election_id
           LEFT JOIN parties p ON p.id = s.winner_party_id
           WHERE s.region_code = ? AND s.office = ?
           ORDER BY e.election_date""",
        (code, office),
    )
    region = q("SELECT code, name FROM regions WHERE code = ?", (code,))
    if not region:
        raise HTTPException(404, f"unknown region: {code}")
    return {"region": region[0], "winners": winners, "trend": trend}


SIDO_CODE = {
    "서울": "11", "부산": "26", "대구": "27", "인천": "28", "광주": "29", "대전": "30",
    "울산": "31", "세종": "36", "경기": "41", "강원": "42", "충북": "43", "충남": "44",
    "전북": "45", "전남": "46", "경북": "47", "경남": "48", "제주": "50",
}


# 선거구명 자연순 정렬: 제N(숫자 오름차순) → 갑을병정 → 가나다…하·거…(중선거구 letter)
_KR = ("가나다라마바사아자차카타파하" "거너더러머버서어저처커터퍼허"
       "고노도로모보소오조초코토포호" "구누두루무부수우주추쿠투푸후")
_GAP = "갑을병정무기경신임계"


def _sgg_sort_key(name):
    import re
    s = (name or "").replace("선거구", "")
    m = re.search(r"제(\d+)$", s)
    if m:
        return (s[:m.start()], 0, int(m.group(1)))
    if s and s[-1] in _GAP:
        return (s[:-1], 1, _GAP.index(s[-1]))
    if len(s) > 1 and s[-1] in _KR:
        return (s[:-1], 2, _KR.index(s[-1]))
    return (s, 3, 0)


def _top_parties(rows, code_field):
    """[(region_key, party, color, seats)] -> region별 {top_parties, winner}."""
    by = {}
    for r in rows:
        by.setdefault(r[code_field], []).append(r)
    out = []
    for key, lst in by.items():
        lst = sorted(lst, key=lambda x: -x["seats"])
        top = lst[0]
        out.append({
            "region_code": top.get("region_code", key),
            "region_name": top.get("region_name", key),
            "winner_party": top["party"], "color_hex": top["color_hex"],
            "winner_seats": top["seats"],
            "top_parties_json": [{"party": x["party"], "color": x["color_hex"], "seats": x["seats"]} for x in lst],
        })
    return out


@api.get("/council/map")
def council_map(hoecha: int, sgtype: int, parent: str | None = None):
    """지방의원 의석 최다 정당색. parent(시도코드) 있으면 시군구, 없으면 시도 단위."""
    if parent is None:
        rows = q(
            "SELECT c.sido, c.party, SUM(c.elected) AS seats, p.color_hex "
            "FROM council c LEFT JOIN parties p ON p.name=c.party "
            "WHERE c.hoecha=? AND c.sgtype=? GROUP BY c.sido, c.party HAVING seats>0",
            (hoecha, sgtype))
        for r in rows:
            r["region_code"] = SIDO_CODE.get(r["sido"], r["sido"])
            r["region_name"] = r["sido"]
        return _top_parties(rows, "sido")
    sido_short = next((s for s, c in SIDO_CODE.items() if c == parent), parent)
    rows = q(
        "SELECT c.sigungu_code, c.sigungu_name, c.party, SUM(c.elected) AS seats, p.color_hex "
        "FROM council c LEFT JOIN parties p ON p.name=c.party "
        "WHERE c.hoecha=? AND c.sgtype=? AND c.sido=? AND c.sigungu_code IS NOT NULL "
        "GROUP BY c.sigungu_code, c.party HAVING seats>0",
        (hoecha, sgtype, sido_short))
    for r in rows:
        r["region_code"] = r["sigungu_code"]
        r["region_name"] = r["sigungu_name"]
    return _top_parties(rows, "sigungu_code")


@api.get("/council/detail")
def council_detail(hoecha: int, sigungu_code: str):
    """시군구의 광역의원·기초의원 선거구별 후보(낙선 포함). 선거구 자연순."""
    rows = q(
        "SELECT c.sgtype, c.sgg, c.idx, c.party, c.name, c.votes, c.rate, c.elected, p.color_hex "
        "FROM council c LEFT JOIN parties p ON p.name=c.party "
        "WHERE c.hoecha=? AND c.sigungu_code=?",
        (hoecha, sigungu_code))
    rows.sort(key=lambda r: (r["sgtype"], _sgg_sort_key(r["sgg"]),
                             0 if r["elected"] else 1, -(r["votes"] or 0)))
    return rows


@api.get("/assembly/sido")
def assembly_sido(daesu: int, sido: str):
    """총선 시도 드릴다운: 해당 시도의 선거구별 후보(낙선 포함), 자연순.
    sido = 시도 코드(예 '11')."""
    short = next((s for s, c in SIDO_CODE.items() if c == sido), sido)
    colors = _party_colors()
    rows = q("SELECT sgg, idx, party, name, votes, rate, elected FROM assembly_sgg "
             "WHERE daesu=? AND sido=?", (daesu, short))
    by = {}
    for r in rows:
        by.setdefault(r["sgg"], []).append(r)
    out = []
    for sgg, cs in by.items():
        cs.sort(key=lambda x: (0 if x["elected"] else 1, -(x["votes"] or 0)))
        for c in cs:
            c["color_hex"] = colors.get(c["party"], "#bbb")
        win = cs[0]
        out.append({"sgg": sgg, "winner_name": win["name"], "winner_party": win["party"],
                    "color_hex": win["color_hex"], "candidates": cs})
    out.sort(key=lambda x: _sgg_sort_key(x["sgg"]))
    return out


PRES_YEAR = {16: 2002, 17: 2007, 18: 2012, 19: 2017, 20: 2022, 21: 2025}


def _pres_cands(daesu):
    return {r["idx"]: r for r in q("SELECT idx, party, name FROM pres_cand WHERE daesu=? ORDER BY idx", (daesu,))}


def _party_colors():
    return {r["name"]: r["color_hex"] for r in q("SELECT name, color_hex FROM parties")}


@api.get("/president/elections")
def president_elections():
    daesu = [r["daesu"] for r in q("SELECT DISTINCT daesu FROM pres_cand ORDER BY daesu")]
    return [{"daesu": d, "year": PRES_YEAR.get(d), "name": f"제{d}대 대통령선거"} for d in daesu]


@api.get("/president/map")
def president_map(daesu: int, parent: str | None = None):
    """대선 지역별 1위 후보 정당색. parent(시도코드) 있으면 시군구, 없으면 시도."""
    cands = _pres_cands(daesu)
    colors = _party_colors()
    level = "시도" if parent is None else "구시군"
    if parent is None:
        rows = q("SELECT region_code, idx, votes, rate FROM pres_region WHERE daesu=? AND level='시도'", (daesu,))
    else:
        rows = q("SELECT pr.region_code, pr.idx, pr.votes, pr.rate FROM pres_region pr "
                 "JOIN regions rg ON rg.code=pr.region_code "
                 "WHERE pr.daesu=? AND pr.level='구시군' AND rg.parent_code=?", (daesu, parent))
    by = {}
    for r in rows:
        by.setdefault(r["region_code"], []).append(r)
    names = {r["code"]: r["name"] for r in q("SELECT code, name FROM regions")}
    out = []
    for code, lst in by.items():
        lst.sort(key=lambda x: -x["votes"])
        w = cands.get(lst[0]["idx"], {})
        wp = w.get("party", "")
        top = [{"party": cands.get(x["idx"], {}).get("party"),
                "name": cands.get(x["idx"], {}).get("name"),
                "color": colors.get(cands.get(x["idx"], {}).get("party"), "#bbb"),
                "rate": x["rate"]} for x in lst[:5]]
        out.append({"region_code": code, "region_name": names.get(code, code),
                    "party_name": wp, "color_hex": colors.get(wp, "#bbb"),
                    "winner_name": w.get("name"), "winner_rate": lst[0]["rate"],
                    "top_parties_json": top})
    return out


@api.get("/president/region")
def president_region(daesu: int, region_code: str):
    """대선 지역 상세: 후보별 득표(전원) + (시군구면) 투표구별."""
    cands = _pres_cands(daesu)
    colors = _party_colors()
    rows = q("SELECT idx, votes, rate FROM pres_region WHERE daesu=? AND region_code=?", (daesu, region_code))
    cand_list = sorted([
        {"idx": r["idx"], "party": cands.get(r["idx"], {}).get("party"),
         "name": cands.get(r["idx"], {}).get("name"), "votes": r["votes"], "rate": r["rate"],
         "color_hex": colors.get(cands.get(r["idx"], {}).get("party"), "#bbb")}
        for r in rows], key=lambda x: -x["votes"])
    precs = q("SELECT dong, unit, tusu, votes_json FROM pres_precinct WHERE daesu=? AND region_code=?",
              (daesu, region_code))
    return {"candidates": cand_list, "precincts": precs}


# 정당 -> 진영(대선 추이용)
CAMP = {
    "민주": {"새천년민주당", "열린우리당", "대통합민주신당", "민주통합당", "더불어민주당",
            "민주당", "새정치민주연합", "새정치국민회의"},
    "보수": {"한나라당", "새누리당", "자유한국당", "미래통합당", "국민의힘", "신한국당"},
    "진보": {"민주노동당", "통합진보당", "정의당", "진보당", "민중연합당"},
    "중도": {"국민의당", "바른정당", "개혁신당", "국민중심당", "창조한국당"},
}
CAMP_COLOR = {"민주": "#152484", "보수": "#E61E2B", "진보": "#D6001C", "중도": "#FF7920", "기타": "#9E9E9E"}


def _camp(party):
    for c, names in CAMP.items():
        if party in names:
            return c
    return "기타"


@api.get("/president/history")
def president_history(region_code: str):
    """역대 대선 지역 1위 + 진영별 득표율 추이(전 대수)."""
    colors = _party_colors()
    rows = q("SELECT pr.daesu, pr.idx, pr.votes, pr.rate, pc.party, pc.name "
             "FROM pres_region pr JOIN pres_cand pc ON pc.daesu=pr.daesu AND pc.idx=pr.idx "
             "WHERE pr.region_code=?", (region_code,))
    by = {}
    for r in rows:
        by.setdefault(r["daesu"], []).append(r)
    winners, trend = [], []
    for daesu in sorted(by):
        lst = sorted(by[daesu], key=lambda x: -x["votes"])
        w = lst[0]
        winners.append({"daesu": daesu, "year": PRES_YEAR.get(daesu),
                        "winner_party": w["party"], "winner_name": w["name"],
                        "color_hex": colors.get(w["party"], "#bbb"), "winner_rate": w["rate"]})
        camp = {"민주": 0, "보수": 0, "진보": 0, "중도": 0}
        for r in lst:
            c = _camp(r["party"])
            if c in camp:
                camp[c] = round(camp[c] + (r["rate"] or 0), 2)
        trend.append({"daesu": daesu, "year": PRES_YEAR.get(daesu), **camp})
    return {"winners": winners, "trend": trend, "camp_color": CAMP_COLOR}


@api.get("/president/national")
def president_national(daesu: int):
    """대선 전국 후보별 득표(시도 합산) — 전국 요약용."""
    cands = _pres_cands(daesu)
    colors = _party_colors()
    rows = q("SELECT idx, SUM(votes) AS votes FROM pres_region WHERE daesu=? AND level='시도' GROUP BY idx", (daesu,))
    tot = sum(r["votes"] for r in rows) or 1
    out = sorted([{"party": cands.get(r["idx"], {}).get("party"),
                   "name": cands.get(r["idx"], {}).get("name"), "votes": r["votes"],
                   "rate": round(r["votes"] / tot * 100, 2),
                   "color_hex": colors.get(cands.get(r["idx"], {}).get("party"), "#bbb")}
                  for r in rows], key=lambda x: -x["votes"])
    return out


@api.get("/summary")
def summary(kind: str, daesu: int | None = None, election_id: int | None = None,
            office: str | None = None, hoecha: int | None = None, sgtype: int | None = None,
            sido: str | None = None, sigungu: str | None = None):
    """선거별 전국 요약(평가). 통일 형식: {title, rows:[{label,color,value,sub}]}."""
    colors = _party_colors()
    if kind == "president":
        cl = president_national(daesu)
        rows = [{"label": f"{c['name']} ({c['party']})", "color": c["color_hex"],
                 "value": c["rate"], "sub": f"{c['votes']:,}표"} for c in cl[:6]]
        gap = round(cl[0]["rate"] - cl[1]["rate"], 2) if len(cl) > 1 else None
        return {"title": f"제{daesu}대 대선 전국", "unit": "%",
                "note": (f"{cl[0]['name']} 당선 · 2위와 {gap}%p차" if gap is not None else ""), "rows": rows}
    if kind == "assembly":
        agg = {}
        for r in q("SELECT top_parties_json FROM region_election_summary WHERE election_id=? AND office='국회의원'", (election_id,)):
            for p in json.loads(r["top_parties_json"] or "[]"):
                agg[p["party"]] = agg.get(p["party"], 0) + (p.get("seats") or 0)
        rows = [{"label": k, "color": colors.get(k, "#bbb"), "value": v, "sub": f"{v}석"}
                for k, v in sorted(agg.items(), key=lambda x: -x[1]) if v]
        return {"title": "총선 지역구 의석(시도 집계)", "unit": "석", "note": "", "rows": rows}
    if kind == "local":
        agg = {}
        for r in q("SELECT p.name, p.color_hex FROM candidates c JOIN parties p ON p.id=c.party_id "
                   "WHERE c.office=? AND c.election_id=? AND c.is_elected=1", (office, election_id)):
            agg.setdefault(r["name"], [0, r["color_hex"]])
            agg[r["name"]][0] += 1
        rows = [{"label": k, "color": v[1] or "#bbb", "value": v[0], "sub": f"{v[0]}명"}
                for k, v in sorted(agg.items(), key=lambda x: -x[1][0])]
        return {"title": f"{office} 당선자 정당분포", "unit": "명", "note": "", "rows": rows}
    if kind == "council":
        where = "hoecha=? AND sgtype=? AND elected=1"
        args = [hoecha, sgtype]
        scope = "전국"
        if sigungu:
            where += " AND sigungu_code=?"
            args.append(sigungu)
            scope = q("SELECT name FROM regions WHERE code=?", (sigungu,))
            scope = scope[0]["name"] if scope else "시군구"
        elif sido:
            short = next((s for s, c in SIDO_CODE.items() if c == sido), sido)
            where += " AND sido=?"
            args.append(short)
            scope = short
        agg = {}
        for r in q(f"SELECT party, COUNT(*) n FROM council WHERE {where} GROUP BY party", tuple(args)):
            agg[r["party"]] = r["n"]
        lab = "광역의원" if sgtype == 5 else "기초의원"
        total = sum(agg.values())
        rows = [{"label": k, "color": colors.get(k, "#bbb"), "value": v, "sub": f"{v}석"}
                for k, v in sorted(agg.items(), key=lambda x: -x[1])]
        return {"title": f"{scope} {lab} 의석", "unit": "석",
                "note": f"총 {total}석" if total else "", "rows": rows}
    if kind == "superintendent":
        agg = {}
        for r in q("SELECT top_parties_json FROM region_election_summary WHERE election_id=? AND office='교육감'", (election_id,)):
            for p in json.loads(r["top_parties_json"] or "[]"):
                agg.setdefault(p["lean"], [0, p["color"]])
                agg[p["lean"]][0] += 1
        rows = [{"label": k, "color": v[1], "value": v[0], "sub": f"{v[0]}명"}
                for k, v in sorted(agg.items(), key=lambda x: -x[1][0])]
        return {"title": "교육감 성향분포", "unit": "명", "note": "", "rows": rows}
    raise HTTPException(400, f"unknown kind: {kind}")


@api.get("/precinct/lookup")
def precinct_lookup(daesu: int, sigungu_code: str, mode: str = "투표구"):
    """대선 투표소(투표구)·읍면동별 종합. mode=투표구|읍면동."""
    cands = _pres_cands(daesu)
    colors = _party_colors()
    clist = [{"idx": i, "party": cands[i]["party"], "name": cands[i]["name"],
              "color_hex": colors.get(cands[i]["party"], "#bbb")} for i in sorted(cands)]
    precs = q("SELECT dong, unit, tusu, votes_json FROM pres_precinct WHERE daesu=? AND region_code=?",
              (daesu, sigungu_code))
    if mode == "읍면동":
        agg = {}
        for p in precs:
            v = json.loads(p["votes_json"])
            a = agg.setdefault(p["dong"] or "기타", {"tusu": 0, "votes": [0] * len(clist)})
            a["tusu"] += p["tusu"] or 0
            for i, x in enumerate(v):
                a["votes"][i] += x
        rows = [{"dong": k, "unit": "(읍면동 계)", "tusu": a["tusu"], "votes": a["votes"]}
                for k, a in agg.items()]
    else:
        rows = [{"dong": p["dong"], "unit": p["unit"], "tusu": p["tusu"],
                 "votes": json.loads(p["votes_json"])} for p in precs]
    return {"candidates": clist, "rows": rows}


@api.get("/assembly/daesu")
def assembly_daesu():
    """투표구별(gukhoe_precinct) 보유 총선 대수 — 투표소 조회용."""
    rows = q("SELECT DISTINCT daesu FROM gukhoe_precinct ORDER BY daesu DESC")
    return [{"daesu": r["daesu"], "name": f"제{r['daesu']}대 국회의원선거"} for r in rows]


@api.get("/assembly/keys")
def assembly_keys(daesu: int, sido: str):
    """총선 시도의 선거구 키 목록(SIDO_SGG) — 투표소 조회 드릴다운. sido=시도코드."""
    short = next((s for s, c in SIDO_CODE.items() if c == sido), sido)
    rows = q("SELECT DISTINCT key FROM gukhoe_cand WHERE daesu=? AND key LIKE ?",
             (daesu, short + " %"))
    out = [{"key": r["key"], "sgg": r["key"].split(" ", 1)[1] if " " in r["key"] else r["key"]}
           for r in rows]
    out.sort(key=lambda x: _sgg_sort_key(x["sgg"]))
    return out


@api.get("/assembly/district")
def assembly_district(daesu: int, key: str):
    """총선 선거구 상세: 후보 전원(낙선 포함) + 투표구별 득표.
    precincts.votes_json 은 후보 idx(0..n-1) 순서의 득표 배열."""
    cands = q(
        "SELECT g.idx, g.party, g.name, g.votes, g.rate, g.elected, p.color_hex "
        "FROM gukhoe_cand g LEFT JOIN parties p ON p.name = g.party "
        "WHERE g.daesu=? AND g.key=? ORDER BY g.votes DESC",
        (daesu, key),
    )
    precs = q(
        "SELECT dong, unit, tusu, votes_json FROM gukhoe_precinct "
        "WHERE daesu=? AND key=?",
        (daesu, key),
    )
    return {"candidates": cands, "precincts": precs}


@api.get("/region/{code}/results")
def region_results(code: str, election_id: int):
    """특정 회차·지역의 후보별 득표 (당선자 카드/표용). 레벨 무관."""
    return q(
        """SELECT r.candidate_id, c.name AS cand, c.party_id, p.name AS party_name,
                  p.color_hex, r.votes, r.vote_rate, c.is_elected
           FROM results r
           JOIN candidates c   ON c.id = r.candidate_id
           LEFT JOIN parties p ON p.id = c.party_id
           WHERE r.region_code = ? AND r.election_id = ?
           ORDER BY c.is_elected DESC, r.vote_rate DESC""",
        (code, election_id),
    )


# API는 /api 프리픽스. 빌드된 프론트(dist)가 있으면 정적 서빙(단일 서버 배포).
app.include_router(api, prefix="/api")
if DIST.exists():
    app.mount("/", StaticFiles(directory=str(DIST), html=True), name="static")
