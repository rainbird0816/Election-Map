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


TIE_COLOR = "#888888"  # 무소속 = 동률(경합)


def _top_parties(rows, code_field):
    """[(region_key, party, color, seats)] -> region별 {top_parties, winner}. 동률이면 경합색."""
    by = {}
    for r in rows:
        by.setdefault(r[code_field], []).append(r)
    out = []
    for key, lst in by.items():
        lst = sorted(lst, key=lambda x: -x["seats"])
        top = lst[0]
        tie = len(lst) > 1 and lst[1]["seats"] == top["seats"]
        out.append({
            "region_code": top.get("region_code", key),
            "region_name": top.get("region_name", key),
            "winner_party": "경합" if tie else top["party"],
            "color_hex": TIE_COLOR if tie else top["color_hex"],
            "winner_seats": top["seats"], "tie": tie,
            "top_parties_json": [{"party": x["party"], "color": x["color_hex"], "seats": x["seats"]} for x in lst],
        })
    return out


@api.get("/council/seats")
def council_seats(hoecha: int, level: str, sido: str | None = None, sigungu: str | None = None):
    """지방의회 구성 의석: metro=광역의원+광역비례(5+8), basic=기초의원+기초비례(6+9). 동률→경합."""
    colors = _party_colors()
    sgtypes = (5, 8) if level == "metro" else (6, 9)
    where = "hoecha=? AND sgtype IN (?,?) AND elected=1"
    args = [hoecha, *sgtypes]
    scope = "전국"
    if sigungu:
        where += " AND sigungu_code=?"
        args.append(sigungu)
        r = q("SELECT name FROM regions WHERE code=?", (sigungu,))
        scope = r[0]["name"] if r else "시군구"
    elif sido:
        short = next((s for s, c in SIDO_CODE.items() if c == sido), sido)
        where += " AND sido=?"
        args.append(short)
        scope = short
    rows = q(f"SELECT party, COUNT(*) n FROM council WHERE {where} GROUP BY party", tuple(args))
    parties = sorted([{"party": r["party"], "color": colors.get(r["party"], "#bbb"), "seats": r["n"]}
                      for r in rows], key=lambda x: -x["seats"])
    total = sum(p["seats"] for p in parties)
    tie = len(parties) > 1 and parties[1]["seats"] == parties[0]["seats"]
    label = "광역의회 (광역의원+비례)" if level == "metro" else "기초의회 (기초의원+비례)"
    return {"scope": scope, "label": label, "total": total, "parties": parties,
            "winner_party": "경합" if tie else (parties[0]["party"] if parties else None),
            "winner_color": TIE_COLOR if tie else (parties[0]["color"] if parties else "#bbb"),
            "tie": tie}


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


@api.get("/council/pr")
def council_pr(hoecha: int, sgtype: int, sido: str | None = None, sigungu: str | None = None):
    """비례대표(광역 8/기초 9) 정당별 의석 + 당선자 명단. sido/sigungu=코드."""
    colors = _party_colors()
    where, args, scope = "hoecha=? AND sgtype=?", [hoecha, sgtype], "전국"
    if sigungu:
        where += " AND sigungu_code=?"
        args.append(sigungu)
        r = q("SELECT name FROM regions WHERE code=?", (sigungu,))
        scope = r[0]["name"] if r else "시군구"
    elif sido:
        short = next((s for s, c in SIDO_CODE.items() if c == sido), sido)
        where += " AND sido=?"
        args.append(short)
        scope = short
    rows = q(f"SELECT party, name FROM council WHERE {where} ORDER BY party, idx", tuple(args))
    by = {}
    for r in rows:
        by.setdefault(r["party"], []).append(r["name"])
    parties = [{"party": p, "color": colors.get(p, "#bbb"), "seats": len(ns), "names": ns}
               for p, ns in by.items()]
    parties.sort(key=lambda x: -x["seats"])
    lab = "광역비례" if sgtype == 8 else "기초비례"
    return {"scope": scope, "label": lab, "total": len(rows), "parties": parties}


# ── 광역 종합: 시군구별 광역단체장·광역비례(metro_sgg, ingest_metro_sgg.py 적재) ──
@api.get("/metro/sgg-map")
def metro_sgg_map(hoecha: int, sido: str):
    """광역 종합 드릴다운: 시도 내 시군구별 광역단체장 최다 득표 정당색(지도 채색)."""
    short = next((s for s, c in SIDO_CODE.items() if c == sido), sido)
    colors = _party_colors()
    rows = q(
        "SELECT sigungu_code, sigungu_name, party, SUM(votes) AS seats FROM metro_sgg "
        "WHERE hoecha=? AND office='광역단체장' AND sido=? GROUP BY sigungu_code, party",
        (hoecha, short))
    for r in rows:
        r["region_code"] = r["sigungu_code"]
        r["region_name"] = r["sigungu_name"]
        r["color_hex"] = colors.get(r["party"], "#bbb")
    return _top_parties(rows, "sigungu_code")


@api.get("/metro/sgg-detail")
def metro_sgg_detail(hoecha: int, sigungu: str):
    """그 시군구의 광역단체장 후보별 득표(낙선 포함, 득표순)."""
    colors = _party_colors()
    rows = q(
        "SELECT party, name, votes, rate FROM metro_sgg "
        "WHERE hoecha=? AND office='광역단체장' AND sigungu_code=? ORDER BY votes DESC",
        (hoecha, sigungu))
    for r in rows:
        r["color_hex"] = colors.get(r["party"], "#bbb")
    return rows


@api.get("/metro/sgg-pr")
def metro_sgg_pr(hoecha: int, sigungu: str):
    """그 시군구의 광역비례 정당별 득표(득표순)."""
    colors = _party_colors()
    rows = q(
        "SELECT party, votes, rate FROM metro_sgg "
        "WHERE hoecha=? AND office='광역비례' AND sigungu_code=? ORDER BY votes DESC",
        (hoecha, sigungu))
    for r in rows:
        r["color_hex"] = colors.get(r["party"], "#bbb")
    return rows


@api.get("/basic/sido-map")
def basic_sido_map(hoecha: int):
    """기초 종합 전국지도: 시도별 기초단체장 최다 당선 정당색."""
    rows = q(
        "SELECT r.parent_code AS sido, p.name AS party, p.color_hex, COUNT(*) AS seats "
        "FROM region_election_summary s "
        "JOIN regions r ON r.code = s.region_code "
        "JOIN parties p ON p.id = s.winner_party_id "
        "WHERE s.election_id = ? AND s.office = '기초단체장' "
        "GROUP BY r.parent_code, s.winner_party_id",
        (hoecha,))
    name_of = {c: s for s, c in SIDO_CODE.items()}
    for r in rows:
        r["region_code"] = r["sido"]
        r["region_name"] = name_of.get(r["sido"], r["sido"])
    return _top_parties(rows, "sido")


PRES_YEAR = {13: 1987, 14: 1992, 15: 1997, 16: 2002, 17: 2007, 18: 2012,
             19: 2017, 20: 2022, 21: 2025}


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
            "민주당", "새정치민주연합", "새정치국민회의", "평화민주당", "통일민주당"},
    "보수": {"한나라당", "새누리당", "자유한국당", "미래통합당", "국민의힘", "신한국당",
            "민주정의당", "민주자유당"},
    "진보": {"민주노동당", "통합진보당", "정의당", "진보당", "민중연합당", "국민승리21"},
    "중도": {"국민의당", "바른정당", "개혁신당", "국민중심당", "창조한국당",
            "신민주공화당", "통일국민당", "국민신당", "신정치개혁당"},
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


_ASM_YEAR = {14: 1992, 15: 1996, 16: 2000, 17: 2004, 18: 2008, 19: 2012, 20: 2016, 21: 2020, 22: 2024}
_HOE_YEAR = {3: 2002, 4: 2006, 5: 2010, 6: 2014, 7: 2018, 8: 2022}


# 계열(lineage) 라벨별 대표색 — 개관 계열 묶기용
LINEAGE_COLOR = {
    "민주당계": "#152484", "보수계(국민의힘)": "#E61E2B", "진보정당계(정의당)": "#E5007F",
    "충청계(자민련/선진당)": "#0F8B8D", "국민의당/제3지대": "#FF7920",
    "무소속": "#888888", "기타/군소정당": "#9E9E9E",
}
ETC_LABEL = "기타/군소정당"


def _lineage_map():
    """정당명 -> 계열 라벨. parties.lineage_id LEFT JOIN party_lineage."""
    rows = q("SELECT p.name, l.label FROM parties p "
             "LEFT JOIN party_lineage l ON l.id = p.lineage_id")
    return {r["name"]: (r["label"] or ETC_LABEL) for r in rows}


@api.get("/overview")
def overview(kind: str, sgtype: int | None = None, office: str | None = None,
             group: str = "lineage"):
    """개관: 회차별 정당/계열 의석·당선·득표 시계열. 프론트가 헤드라인·Δ·추이·판단 렌더.
    group=lineage(계열별, 개명·통합 정당 묶음) | party(개별 정당)."""
    colors = _party_colors()
    lin = _lineage_map()
    raw = []   # [{id,label,year, agg:{name:value}}]

    if kind == "assembly":
        for d in range(14, 23):
            rows = q("SELECT party, COUNT(*) n FROM assembly_sgg WHERE daesu=? AND elected=1 GROUP BY party", (d,))
            raw.append({"id": d, "label": f"{d}대", "year": _ASM_YEAR[d],
                        "agg": {r["party"]: r["n"] for r in rows if r["n"]}})
        unit = "석"
    elif kind == "council":
        for h in range(3, 9):
            rows = q("SELECT party, COUNT(*) n FROM council WHERE hoecha=? AND sgtype=? AND elected=1 GROUP BY party", (h, sgtype))
            raw.append({"id": h, "label": f"{h}회", "year": _HOE_YEAR[h],
                        "agg": {r["party"]: r["n"] for r in rows if r["n"]}})
        unit = "석"
    elif kind == "local":
        for h in range(3, 9):
            rows = q("SELECT p.name party, COUNT(*) n FROM candidates c JOIN parties p ON p.id=c.party_id "
                     "WHERE c.office=? AND c.election_id=? AND c.is_elected=1 GROUP BY p.name", (office, h))
            raw.append({"id": h, "label": f"{h}회", "year": _HOE_YEAR[h],
                        "agg": {r["party"]: r["n"] for r in rows if r["n"]}})
        unit = "명"
    elif kind == "president":
        for d in range(13, 22):
            cands = _pres_cands(d)
            rows = q("SELECT idx, SUM(votes) v FROM pres_region WHERE daesu=? AND level='시도' GROUP BY idx", (d,))
            if not rows:
                continue
            agg = {}
            for r in rows:
                p = cands.get(r["idx"], {}).get("party")
                if p:
                    agg[p] = agg.get(p, 0) + (r["v"] or 0)
            tot = sum(agg.values()) or 1
            raw.append({"id": d, "label": f"{d}대", "year": PRES_YEAR[d],
                        "agg": {k: round(v / tot * 100, 1) for k, v in agg.items()}})
        unit = "%"
    else:
        raise HTTPException(400, f"unknown kind: {kind}")

    series = []
    for s in raw:
        bucket = {}
        for name, val in s["agg"].items():
            if group == "lineage":
                key = lin.get(name, ETC_LABEL)
                color = LINEAGE_COLOR.get(key, "#9E9E9E")
            else:
                key, color = name, colors.get(name, "#bbb")
            b = bucket.setdefault(key, {"party": key, "color": color, "seats": 0})
            b["seats"] = round(b["seats"] + val, 1) if unit == "%" else b["seats"] + val
        ps = sorted(bucket.values(), key=lambda x: -x["seats"])
        if ps:
            series.append({"id": s["id"], "label": s["label"], "year": s["year"], "parties": ps})
    return {"kind": kind, "unit": unit, "group": group, "series": series}


@api.get("/precinct/trend")
def precinct_trend(sigungu: str, dong: str):
    """대선 읍면동(투표구) 연도별 진영 득표율 추이 — 투표소 클릭 시."""
    out = []
    for daesu in sorted(PRES_YEAR):
        cands = _pres_cands(daesu)
        rows = q("SELECT votes_json FROM pres_precinct WHERE daesu=? AND region_code=? AND dong=?",
                 (daesu, sigungu, dong))
        if not rows:
            continue
        camp = {"민주": 0, "보수": 0, "진보": 0, "중도": 0}
        total = 0
        for r in rows:
            try:
                v = json.loads(r["votes_json"])
            except Exception:
                continue
            for idx, val in enumerate(v):
                total += val or 0
                c = _camp(cands.get(idx, {}).get("party"))
                if c in camp:
                    camp[c] += val or 0
        if not total:
            continue
        out.append({"daesu": daesu, "year": PRES_YEAR[daesu],
                    **{k: round(camp[k] / total * 100, 2) for k in camp}})
    return {"trend": out, "camp_color": CAMP_COLOR}


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


# ── 보궐선거(재·보궐 + 정규선거일 동시보궐) — ingest_byelection.py 적재 ──
@api.get("/byelection/list")
def byelection_list():
    """보궐선거 선거일 목록 + 선거일별 직종 요약(선거구·당선 수). 최신순."""
    rows = q("SELECT sg_id, vote_date, label, kind, sgtype, sgtype_name, sido, sgg, elected "
             "FROM byelection")
    by = {}
    for r in rows:
        d = by.setdefault(r["sg_id"], {
            "sg_id": r["sg_id"], "vote_date": r["vote_date"],
            "label": r["label"], "kind": r["kind"], "offices": {}})
        o = d["offices"].setdefault(r["sgtype"], {
            "sgtype": r["sgtype"], "name": r["sgtype_name"], "races": set(), "seats": 0})
        o["races"].add((r["sido"], r["sgg"]))
        o["seats"] += r["elected"] or 0
    out = []
    for d in by.values():
        offices = sorted(d["offices"].values(), key=lambda x: x["sgtype"])
        for o in offices:
            o["races"] = len(o["races"])
        out.append({**d, "offices": offices,
                    "total_races": sum(o["races"] for o in offices),
                    "total_seats": sum(o["seats"] for o in offices)})
    out.sort(key=lambda x: x["vote_date"], reverse=True)
    return out


@api.get("/byelection/detail")
def byelection_detail(sg_id: str, sgtype: int):
    """보궐선거 한 직종의 선거구별 후보 전원(낙선 포함). 시도→선거구 자연순."""
    colors = _party_colors()
    rows = q("SELECT sido, sgg, region, idx, party, name, votes, rate, elected "
             "FROM byelection WHERE sg_id=? AND sgtype=?", (sg_id, sgtype))
    by = {}
    for r in rows:
        by.setdefault((r["sido"], r["sgg"]), []).append(r)
    out = []
    for (sido, sgg), cs in by.items():
        cs.sort(key=lambda x: (0 if x["elected"] else 1, -(x["votes"] or 0)))
        for c in cs:
            c["color_hex"] = colors.get(c["party"], "#bbb")
        winners = [c for c in cs if c["elected"]]
        win = winners[0] if winners else cs[0]
        out.append({
            "sido": sido, "sgg": sgg, "region": cs[0]["region"],
            "winner_name": " · ".join(c["name"] for c in winners) if winners else win["name"],
            "winner_party": win["party"], "color_hex": win["color_hex"],
            "seats": len(winners), "candidates": cs})
    out.sort(key=lambda x: (x["sido"], _sgg_sort_key(x["sgg"])))
    return out


# ── 당선인 매트릭스: 전국(광역단체장)→광역(기초단체장)→기초, 연도별 당선인만 ──
@api.get("/winners")
def winners(level: str = "metro", parent: str | None = None):
    """단체장 당선인을 지역×회차 매트릭스로. level=metro(시도×회차 광역단체장),
    basic(parent 시도의 시군구×회차 기초단체장). 셀 색=단체장 정당색."""
    office = "광역단체장" if level == "metro" else "기초단체장"
    sql = """SELECT s.region_code, r.name AS region_name, r.parent_code,
                    e.id AS election_id, e.hoecha, e.election_date,
                    ca.name AS winner_name, p.name AS party, p.color_hex
             FROM region_election_summary s
             JOIN elections e        ON e.id = s.election_id
             LEFT JOIN regions r     ON r.code = s.region_code
             LEFT JOIN candidates ca ON ca.id = s.winner_candidate_id
             LEFT JOIN parties p     ON p.id = s.winner_party_id
             WHERE s.office = ?"""
    args = [office]
    if level == "basic":
        if not parent:
            raise HTTPException(400, "basic level requires parent (시도코드)")
        sql += " AND r.parent_code = ?"
        args.append(parent)
    rows = q(sql, tuple(args))

    cols = {}
    by = {}
    for r in rows:
        cols[r["election_id"]] = {"election_id": r["election_id"], "hoecha": r["hoecha"],
                                 "year": (r["election_date"] or "")[:4]}
        reg = by.setdefault(r["region_code"], {
            "region_code": r["region_code"], "region_name": r["region_name"],
            "parent_code": r["parent_code"], "cells": {}})
        reg["cells"][r["election_id"]] = {
            "name": r["winner_name"], "party": r["party"],
            "color_hex": r["color_hex"] or "#bbb"}
    columns = sorted(cols.values(), key=lambda c: c["election_id"])

    if level == "metro":
        order = {c: i for i, c in enumerate(SIDO_CODE.values())}
        regions = sorted(by.values(), key=lambda x: order.get(x["region_code"], 99))
    else:
        regions = sorted(by.values(), key=lambda x: x["region_code"])
    return {"office": office, "columns": columns, "regions": regions}


# API는 /api 프리픽스. 빌드된 프론트(dist)가 있으면 정적 서빙(단일 서버 배포).
app.include_router(api, prefix="/api")
if DIST.exists():
    app.mount("/", StaticFiles(directory=str(DIST), html=True), name="static")
