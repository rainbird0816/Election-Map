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


def collect_winners(cli, ec, sidos):
    """당선인 명부(무투표 포함) 전국 수집 -> nec9_ec{ec}_win.json.
    지역구(5/6)는 시도→구시군 순회, 비례(8/9)는 시도 단위."""
    is_pr = ec in ("8", "9")
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
