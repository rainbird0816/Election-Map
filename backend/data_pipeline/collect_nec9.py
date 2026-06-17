"""제9회 지방선거(2026-06-03) 선관위 선거통계시스템(info.nec.go.kr) 개표결과 수집.

OpenAPI 미공개 / 정제본 미공개 단계의 잠정 수집 경로.
info.nec.go.kr 의 electionInfo_report.xhtml 를 직접 POST 재현(세션 쿠키만 필요).
계단식: 선거종류(electionCode) → 시도(cityCode) → 구시군(townCode) → 결과표(table01).

electionCode: 3=시도지사 4=구시군장 5=시도의원지역구 6=구시군의원지역구
              8=광역의원비례 9=기초의원비례 11=교육감
출력: data/raw/nec9_<office>.json  (council ingest 형식에 맞춰 후처리)

실행: python backend/data_pipeline/collect_nec9.py 5     # 시도의회의원 지역구
"""
import io
import json
import pathlib
import sys
import time
import warnings

import httpx
import pandas as pd

warnings.filterwarnings("ignore")
ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "data" / "raw"
BASE = "https://info.nec.go.kr"
EID = "0020260603"
HDR = {"User-Agent": "Mozilla/5.0"}

# 선관위 시도코드 -> 행정표준코드(우리 DB)
SIDO_NEC2STD = {
    "1100": "11", "2600": "26", "2700": "27", "2800": "28", "2900": "29",
    "3000": "30", "3100": "31", "5100": "36", "4100": "41", "5200": "42",
    "4300": "43", "4400": "44", "5300": "45", "4600": "46", "4700": "47",
    "4800": "48", "4900": "50",
}
# townCode 앞 2자리 -> 행정표준 시도코드 (통합 광주(2900) 아래 전남 시군구 자동 분리용)
TOWN2STD = {
    "11": "11", "26": "26", "27": "27", "28": "28", "29": "29", "30": "30",
    "31": "31", "41": "41", "43": "43", "44": "44", "46": "46", "47": "47",
    "48": "48", "51": "36", "52": "42", "53": "45", "49": "50",
}
# secondMenuId 는 개표진행상황(VCCP09) 공통. statementId = {menuId}_#{electionCode}_0
MENU = "VCCP09"
REQ_URI = f"/electioninfo/{EID}/vc/vccp09.jsp"


def new_client():
    cli = httpx.Client(timeout=60, verify=False, headers=HDR, follow_redirects=True)
    cli.get(f"{BASE}/main/showDocument.xhtml?electionId={EID}&topMenuId=VC&secondMenuId={MENU}")
    return cli


def get_towns(cli, election_code, city):
    """시도 -> 구시군 목록 [(code,name)]. 단층(세종 등)은 빈 리스트."""
    r = cli.post(f"{BASE}/bizcommon/selectbox/selectbox_townCodeByCityIntgSgJson.json",
                 data={"electionId": EID, "electionCode": election_code, "cityCode": city})
    body = r.json().get("jsonResult", {}).get("body", []) or []
    return [(b["CODE"], b["NAME"]) for b in body]


def fetch_report(cli, election_code, city, town):
    data = {
        "electionId": EID, "requestURI": REQ_URI, "topMenuId": "VC",
        "secondMenuId": MENU, "menuId": MENU, "statementId": f"{MENU}_#{election_code}_0",
        "electionCode": election_code, "cityCode": city, "sggCityCode": "0",
        "townCode": town, "sggTownCode": "0",
    }
    return cli.post(f"{BASE}/electioninfo/electionInfo_report.xhtml", data=data).text


# 당선인 명부(EPEI01): 선거구별 당선자(무투표 포함). 컬럼 구시군|선거구|정당|사진|성명|...|득표수(득표율)
WIN_URI = f"/electioninfo/{EID}/ep/epei01.jsp"


def fetch_winners(cli, election_code, city, town):
    data = {
        "electionId": EID, "requestURI": WIN_URI, "topMenuId": "EP",
        "secondMenuId": "EPEI01", "menuId": "EPEI01", "statementId": f"EPEI01_#{election_code}",
        "electionCode": election_code, "cityCode": city, "townCode": town,
        "sggTownCode": "0", "proportionalRepresentationCode": "0",
    }
    return cli.post(f"{BASE}/electioninfo/electionInfo_report.xhtml", data=data).text


def parse_winners(html):
    """당선인 명부 파싱. 반환 [{sigungu, sgname, party, name, votes, rate, uncontested}]."""
    import re
    try:
        df = pd.read_html(io.StringIO(html))[0]
    except (ValueError, IndexError):
        return []
    df.columns = range(len(df.columns))
    out = []
    for _, r in df.iterrows():
        sgname = r[1]
        if not (isinstance(sgname, str) and sgname.strip()) or "결과가 없습니다" in sgname:
            continue
        name = re.sub(r"\s*\(.*?\)\s*$", "", str(r[4])).strip()
        last = str(r[len(df.columns) - 1])
        unc = "무투표" in last
        votes = rate = None
        if not unc:
            m = re.search(r"([\d,]+)\s*\(([\d.]+)\)", last)
            if m:
                votes, rate = int(m.group(1).replace(",", "")), float(m.group(2))
        out.append({"sigungu": (r[0].strip() if isinstance(r[0], str) else None),
                    "sgname": sgname.strip(), "party": str(r[2]).strip(),
                    "name": name, "votes": votes, "rate": rate, "uncontested": unc})
    return out


def _num(v, cast):
    try:
        return cast(v) if pd.notna(v) else None
    except (ValueError, TypeError):
        return None


def parse_districts(html):
    """선거구별 후보 파싱. 반환 (contested, uncontested):
       contested: [{sigungu, sgname, cands:[{party,name,votes,rate}]}]
       uncontested: [{sigungu, sgname}]  # 무투표선거구(당선자는 당선인 메뉴에서 보강)

    표 구조: 일반 선거구는 3행 묶음
      행A: [구시군명|NaN, NaN, ..., 후보들(정당 이름), '계']
      행B(득표수): [NaN, 선거구명, 선거인수, 투표수, 득표수..., 계, 무효, 기권, 개표율]
      행C: [NaN, NaN, ..., 득표율...]
    무투표선거구: 한 행에 [구시군명, '○○선거구 (무투표선거구)', NaN...].
    구시군명은 rowspan 병합되어 비는 경우가 있어 forward-fill 한다.
    """
    try:
        df = pd.read_html(io.StringIO(html))[0]
    except (ValueError, IndexError):
        return [], []
    df.columns = range(len(df.columns))
    rows = df.values.tolist()
    contested, uncontested = [], []
    last_sgu = None
    for idx, row in enumerate(rows):
        c0, c1, c2 = row[0], row[1], row[2]
        if isinstance(c0, str) and c0.strip():
            last_sgu = c0.strip()
        if not (isinstance(c1, str) and c1.strip()):
            continue
        if "무투표" in c1:
            uncontested.append({"sigungu": last_sgu, "sgname": c1.split("(")[0].strip()})
            continue
        if pd.isna(c2):           # 선거인수 없는 행 = 득표수행 아님
            continue
        ra = rows[idx - 1] if idx > 0 else [None] * len(row)
        rc = rows[idx + 1] if idx + 1 < len(rows) else [None] * len(row)
        cands = []
        for j in range(4, len(row)):       # 후보는 col4부터
            cell = ra[j] if j < len(ra) else None
            if isinstance(cell, str) and cell.strip() and cell.strip() != "계":
                parts = cell.strip().rsplit(" ", 1)
                party, name = (parts[0], parts[1]) if len(parts) == 2 else ("무소속", parts[0])
                cands.append({"party": party, "name": name,
                              "votes": _num(row[j], int),
                              "rate": _num(rc[j] if j < len(rc) else None, float)})
        if cands:
            contested.append({"sigungu": last_sgu, "sgname": c1.strip(), "cands": cands})
    return contested, uncontested


def parse_pr_winners(html):
    """비례대표 당선인 명부 파싱. 컬럼 시도|정당|사진|성명|... → [{party, name}]."""
    import re
    try:
        df = pd.read_html(io.StringIO(html))[0]
    except (ValueError, IndexError):
        return []
    df.columns = range(len(df.columns))
    out = []
    for _, r in df.iterrows():
        if not (isinstance(r[0], str) and r[0].strip()) or "결과가 없습니다" in r[0]:
            continue
        name = re.sub(r"\s*\(.*?\)\s*$", "", str(r[4])).strip()
        out.append({"sido_name": r[0].strip(), "party": str(r[1]).strip(), "name": name})
    return out


# 비례 시도명 -> 행정표준코드 (통합특별시는 임시코드 49)
PR_SIDO2STD = {
    "서울특별시": "11", "부산광역시": "26", "대구광역시": "27", "인천광역시": "28",
    "광주광역시": "29", "대전광역시": "30", "울산광역시": "31", "세종특별자치시": "36",
    "경기도": "41", "강원특별자치도": "42", "충청북도": "43", "충청남도": "44",
    "전북특별자치도": "45", "전라남도": "46", "경상북도": "47", "경상남도": "48",
    "제주특별자치도": "50", "전남광주통합특별시": "49",
}


# ── 기초단체장(ec4)·기초비례(ec9): 구시군 단위라 시도(town=0)로 일괄 조회 ──
def parse_local_gov_winners(html):
    """기초단체장 당선인. 컬럼 구시군|정당|사진|성명(한자)|성별|…|득표수(율).
    구시군마다 1명. 반환 [{sigungu, party, name, votes, rate, uncontested}]."""
    import re
    try:
        df = pd.read_html(io.StringIO(html))[0]
    except (ValueError, IndexError):
        return []
    df.columns = range(len(df.columns))
    out = []
    for _, r in df.iterrows():
        sgu = r[0]
        if not (isinstance(sgu, str) and sgu.strip()) or "결과가 없" in sgu:
            continue
        name = re.sub(r"\s*\(.*?\)\s*$", "", str(r[3])).strip()
        last = str(r[len(df.columns) - 1])
        unc = "무투표" in last
        votes = rate = None
        if not unc:
            m = re.search(r"([\d,]+)\s*\(([\d.]+)\)", last)
            if m:
                votes, rate = int(m.group(1).replace(",", "")), float(m.group(2))
        out.append({"sigungu": sgu.strip(), "party": str(r[1]).strip(),
                    "name": name, "votes": votes, "rate": rate, "uncontested": unc})
    return out


def parse_basic_pr_winners(html):
    """기초의원 비례 당선인. 컬럼 구시군|정당|순번|사진|성명(한자)|…. 득표 없음.
    반환 [{sigungu, party, name}]."""
    import re
    try:
        df = pd.read_html(io.StringIO(html))[0]
    except (ValueError, IndexError):
        return []
    df.columns = range(len(df.columns))
    out = []
    for _, r in df.iterrows():
        sgu = r[0]
        if not (isinstance(sgu, str) and sgu.strip()) or "결과가 없" in sgu:
            continue
        name = re.sub(r"\s*\(.*?\)\s*$", "", str(r[4])).strip()
        out.append({"sigungu": sgu.strip(), "party": str(r[1]).strip(), "name": name})
    return out


def collect_local_gov(cli, sidos):
    """기초단체장(ec4) 전국 당선인 → nec9_ec4_win.json. 시도(town=0)로 일괄."""
    wins = []
    for city, cname in sidos:
        std0 = SIDO_NEC2STD.get(city)
        n = 0
        for w in parse_local_gov_winners(fetch_winners(cli, "4", city, "0")):
            std = ("29" if w["sigungu"] in GWANGJU_GU else "46") if city == "2900" else std0
            wins.append({"sido_std": std, "town_nec": city, **w})
            n += 1
        time.sleep(0.12)
        print(f"  {cname}: 기초단체장 {n}")
    out = OUT / "nec9_ec4_win.json"
    out.write_text(json.dumps({"electionId": EID, "electionCode": "4", "hoecha": 9,
                               "source": "info.nec.go.kr 당선인 명부(잠정).", "winners": wins},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"기초단체장 당선인: {len(wins)} (무투표 {sum(1 for w in wins if w['uncontested'])}) → {out.name}")


def collect_basic_pr(cli, sidos):
    """기초비례(ec9) 전국 당선인 → nec9_ec9_win.json. 시도(town=0)로 일괄(구시군별)."""
    wins = []
    for city, cname in sidos:
        std0 = SIDO_NEC2STD.get(city)
        n = 0
        for w in parse_basic_pr_winners(fetch_winners(cli, "9", city, "0")):
            std = ("29" if w["sigungu"] in GWANGJU_GU else "46") if city == "2900" else std0
            wins.append({"sido_std": std, "town_nec": city, **w, "uncontested": False})
            n += 1
        time.sleep(0.12)
        print(f"  {cname}: 기초비례 당선 {n}")
    out = OUT / "nec9_ec9_win.json"
    out.write_text(json.dumps({"electionId": EID, "electionCode": "9", "hoecha": 9,
                               "source": "info.nec.go.kr 당선인 명부(잠정).", "winners": wins},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"기초비례 당선인: {len(wins)} → {out.name}")


def collect_winners(cli, ec, sidos):
    """당선인 명부(무투표 포함) 전국 수집 -> nec9_ec{ec}_win.json.
    지역구(5/6)는 시도→구시군 순회, 광역비례(8)는 시도 단위,
    기초단체장(4)·기초비례(9)는 시도(town=0) 일괄(구시군별)."""
    if ec == "4":
        return collect_local_gov(cli, sidos)
    if ec == "9":
        return collect_basic_pr(cli, sidos)
    is_pr = ec == "8"
    wins = []
    for city, cname in sidos:
        std = SIDO_NEC2STD.get(city)
        if is_pr:
            got = 0
            for w in parse_pr_winners(fetch_winners(cli, ec, city, "0")):
                wstd = PR_SIDO2STD.get(w["sido_name"], std)  # 통합특별시→49
                wins.append({"sido_std": wstd, "town_nec": city, **w, "uncontested": False})
                got += 1
            time.sleep(0.12)
            print(f"  {cname}: 비례당선 {got}")
            continue
        towns = get_towns(cli, ec, city) or [(city, cname)]
        n = 0
        for tcode, tname in towns:
            for w in parse_winners(fetch_winners(cli, ec, city, tcode)):
                wins.append({"sido_std": TOWN2STD.get(str(tcode)[:2], std), "town_nec": tcode, **w})
                n += 1
            time.sleep(0.12)
        print(f"  {cname}: 당선 {n}")
    out = OUT / f"nec9_ec{ec}_win.json"
    out.write_text(json.dumps({"electionId": EID, "electionCode": ec, "hoecha": 9,
                               "source": "info.nec.go.kr 당선인 명부(잠정).", "winners": wins},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    nu = sum(1 for w in wins if w["uncontested"])
    print(f"electionCode {ec} 당선인: {len(wins)} (무투표 {nu}) → {out.name}")


def fetch_pr_sgg(cli, city):
    """광역비례(ec8) 시군구별 정당 득표. townCode=-1로 시도 전체 시군구 일괄. statementId=VCCP09_#8."""
    data = {
        "electionId": EID, "requestURI": REQ_URI, "topMenuId": "VC",
        "secondMenuId": MENU, "menuId": MENU, "statementId": f"{MENU}_#8",
        "electionCode": "8", "cityCode": city, "sggCityCode": "0",
        "townCode": "-1", "sggTownCode": "0",
    }
    return cli.post(f"{BASE}/electioninfo/electionInfo_report.xhtml", data=data).text


# 통합 광주(2900) 결과 분리용 — 광주 5개 자치구(나머지는 전남)
GWANGJU_GU = {"동구", "서구", "남구", "북구", "광산구"}


def parse_pr_sgg(html):
    """광역비례 시군구별 정당 득표 파싱 → [{sigungu, party, votes, rate}].
    구조: 정당명 행(col3~ '계' 전) + 시군구마다 득표수행/득표율행 2행. '합계' 행 제외."""
    try:
        df = pd.read_html(io.StringIO(html))[0]
    except (ValueError, IndexError):
        return []
    df.columns = range(len(df.columns))
    rows = df.values.tolist()
    prow = next((r for r in rows if any(isinstance(x, str) and "더불어민주당" in x for x in r)), None)
    if not prow:
        return []
    parties = {j: prow[j].strip() for j in range(len(prow))
               if isinstance(prow[j], str) and prow[j].strip() and prow[j].strip() != "계"}
    out = []
    for idx, r in enumerate(rows):
        sgu = r[0]
        if not (isinstance(sgu, str) and sgu.strip()) or sgu.strip() in ("합계", "계"):
            continue
        if pd.isna(r[1]):  # 선거인수 없는 행(정당명/율행)
            continue
        rr = rows[idx + 1] if idx + 1 < len(rows) else None
        for j, party in parties.items():
            out.append({"sigungu": sgu.strip(), "party": party,
                        "votes": _num(r[j], int),
                        "rate": _num(rr[j] if rr else None, float)})
    return out


def fetch_gov_sgg(cli, city):
    """광역단체장(ec3) 시군구별 후보 득표. townCode=-1 시도 전체. statementId=VCCP09_#3."""
    data = {
        "electionId": EID, "requestURI": REQ_URI, "topMenuId": "VC",
        "secondMenuId": MENU, "menuId": MENU, "statementId": f"{MENU}_#3",
        "electionCode": "3", "cityCode": city, "sggCityCode": "0",
        "townCode": "-1", "sggTownCode": "0",
    }
    return cli.post(f"{BASE}/electioninfo/electionInfo_report.xhtml", data=data).text


def parse_gov_sgg(html):
    """광역단체장 시군구별 후보 득표 → [{sigungu, party, name, votes, rate}].
    후보 행(col3~)은 '정당 이름' 형식. 시군구마다 득표수행/득표율행 2행. '합계' 제외."""
    try:
        df = pd.read_html(io.StringIO(html))[0]
    except (ValueError, IndexError):
        return []
    df.columns = range(len(df.columns))
    rows = df.values.tolist()
    crow = next((r for r in rows if any(isinstance(x, str) and (" " in x and any(
        p in x for p in ("더불어민주당", "국민의힘", "무소속"))) for x in r)), None)
    if not crow:
        return []
    cols = {j: crow[j].strip() for j in range(len(crow))
            if isinstance(crow[j], str) and crow[j].strip() and crow[j].strip() != "계"}
    out = []
    for idx, r in enumerate(rows):
        sgu = r[0]
        if not (isinstance(sgu, str) and sgu.strip()) or sgu.strip() in ("합계", "계"):
            continue
        if pd.isna(r[1]):
            continue
        rr = rows[idx + 1] if idx + 1 < len(rows) else None
        for j, label in cols.items():
            parts = label.rsplit(" ", 1)
            party, name = (parts[0], parts[1]) if len(parts) == 2 else (label, None)
            out.append({"sigungu": sgu.strip(), "party": party, "name": name,
                        "votes": _num(r[j], int), "rate": _num(rr[j] if rr else None, float)})
    return out


def collect_gov_sgg(cli, sidos):
    """광역단체장 시군구별 후보 득표 전국 수집 → nec9_ec3_sgg.json."""
    rows = []
    for city, cname in sidos:
        std0 = SIDO_NEC2STD.get(city)
        for d in parse_gov_sgg(fetch_gov_sgg(cli, city)):
            std = ("29" if d["sigungu"] in GWANGJU_GU else "46") if city == "2900" else std0
            rows.append({"sido_std": std, **d})
        time.sleep(0.12)
        print(f"  {cname}: 누적 {len(rows)}")
    out = OUT / "nec9_ec3_sgg.json"
    out.write_text(json.dumps({"electionId": EID, "hoecha": 9,
                               "source": "info.nec.go.kr 개표진행상황 광역단체장 시군구별(잠정).", "rows": rows},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"광역단체장 시군구별 득표: {len(rows)}행 → {out.name}")


def collect_pr_sgg(cli, sidos):
    """광역비례 시군구별 정당 득표 전국 수집 → nec9_ec8_sgg.json."""
    rows = []
    for city, cname in sidos:
        std0 = SIDO_NEC2STD.get(city)
        for d in parse_pr_sgg(fetch_pr_sgg(cli, city)):
            # 통합 광주(2900): 광주 5구→29, 나머지→전남46
            if city == "2900":
                std = "29" if d["sigungu"] in GWANGJU_GU else "46"
            else:
                std = std0
            rows.append({"sido_std": std, **d})
        time.sleep(0.12)
        print(f"  {cname}: {sum(1 for r in rows if r['sido_std'] in (std0, '29', '46'))}")
    out = OUT / "nec9_ec8_sgg.json"
    out.write_text(json.dumps({"electionId": EID, "hoecha": 9,
                               "source": "info.nec.go.kr 개표진행상황 광역비례 시군구별(잠정).", "rows": rows},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"광역비례 시군구별 득표: {len(rows)}행 → {out.name}")


# ── 기초단체장(ec4) 개표 tally(후보 전원): 시도(town=-1)로 일괄, parse_districts 재사용 ──
def fetch_local_gov_tally(cli, city):
    """기초단체장 시도 전체 개표결과. townCode=-1, statementId VCCP09_#4.
    구시군마다 1개 race(parse_districts의 '선거구'로 파싱). 통합 없이 시도별 분리."""
    data = {
        "electionId": EID, "requestURI": REQ_URI, "topMenuId": "VC",
        "secondMenuId": MENU, "menuId": MENU, "statementId": f"{MENU}_#4",
        "electionCode": "4", "cityCode": city, "sggCityCode": "0",
        "townCode": "-1", "sggTownCode": "0",
    }
    return cli.post(f"{BASE}/electioninfo/electionInfo_report.xhtml", data=data).text


def collect_gov_tally(cli, sidos):
    """기초단체장 후보 전원(낙선 포함) 전국 수집 → nec9_ec4.json.
    cityCode 드롭다운에 광주(2900)·전남(4600)이 분리돼 있어 시도별 town=-1 로 일괄."""
    rows, unc = [], []
    for city, cname in sidos:
        std = SIDO_NEC2STD.get(city)
        ct, uc = parse_districts(fetch_local_gov_tally(cli, city))
        for d in ct:
            rows.append({"sido_std": std, "town_nec": city, **d})
        for u in uc:
            unc.append({"sido_std": std, "town_nec": city, **u})
        time.sleep(0.12)
        print(f"  {cname}: 경합 {len(ct)} / 무투표 {len(uc)}")
    out = OUT / "nec9_ec4.json"
    out.write_text(json.dumps({"electionId": EID, "electionCode": "4", "hoecha": 9,
                               "source": "info.nec.go.kr 개표진행상황 기초단체장(잠정).",
                               "rows": rows, "uncontested": unc}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    tot = sum(len(r["cands"]) for r in rows)
    print(f"기초단체장 개표: 경합 {len(rows)}(후보 {tot}) / 무투표 {len(unc)} → {out.name}")


def main():
    ec = sys.argv[1] if len(sys.argv) > 1 else "5"
    mode = sys.argv[2] if len(sys.argv) > 2 else "tally"
    cli = new_client()
    # 시도 목록
    import re
    page = cli.get(f"{BASE}/main/showDocument.xhtml?electionId={EID}&topMenuId=VC&secondMenuId={MENU}").text
    m = re.search(r'<select[^>]*id="cityCode".*?</select>', page, re.S)
    sidos = [(v, lab.strip()) for v, lab in
             re.findall(r'<option[^>]*value="([^"]*)"[^>]*>([^<]*)</option>', m.group(0))
             if v in SIDO_NEC2STD]

    if mode == "win":
        collect_winners(cli, ec, sidos)
        return
    if mode == "sggpr":
        collect_pr_sgg(cli, sidos)
        return
    if mode == "sggov":
        collect_gov_sgg(cli, sidos)
        return
    if ec == "4":  # 기초단체장 개표 tally는 시도(town=-1) 일괄 전용
        collect_gov_tally(cli, sidos)
        return

    all_rows, all_unc = [], []
    for city, cname in sidos:
        towns = get_towns(cli, ec, city)
        if not towns:  # 단층(세종 등) — 시도 자체로 조회
            towns = [(city, cname)]
        nc = nu = 0
        for tcode, tname in towns:
            html = fetch_report(cli, ec, city, tcode)
            contested, uncontested = parse_districts(html)
            std = TOWN2STD.get(str(tcode)[:2], SIDO_NEC2STD.get(city))  # 통합시→town 앞2자리로 분리
            for d in contested:
                all_rows.append({"sido_std": std, "town_nec": tcode, **d})
                nc += 1
            for u in uncontested:
                all_unc.append({"sido_std": std, "town_nec": tcode, **u})
                nu += 1
            time.sleep(0.12)
        print(f"  {cname}: 구시군 {len(towns)} → 경합 {nc} / 무투표 {nu}")

    out_path = OUT / f"nec9_ec{ec}.json"
    out_path.write_text(json.dumps(
        {"electionId": EID, "electionCode": ec, "hoecha": 9,
         "source": "info.nec.go.kr 개표진행상황(잠정). 정제본 공개 시 교체.",
         "rows": all_rows, "uncontested": all_unc}, ensure_ascii=False, indent=1), encoding="utf-8")
    tot_cand = sum(len(r["cands"]) for r in all_rows)
    print(f"electionCode {ec}: 경합선거구 {len(all_rows)}(후보 {tot_cand}) / 무투표선거구 {len(all_unc)} → {out_path.name}")


if __name__ == "__main__":
    main()
