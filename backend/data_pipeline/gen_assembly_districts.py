"""국회의원 선거구 TopoJSON의 각 선거구에 당선 정당 배정 (21·22대).

규칙: 석권 시도(SWEEP) + 그 외는 다수당(DEFAULT)에 소수당 집합(MINORITY)만 예외.
시도별 의석수(EXPECTED)로 전수 검증. 출력: frontend/public/geo/assembly-{대수}-winners.json
실행: python backend/data_pipeline/gen_assembly_districts.py
"""
import json
import pathlib
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
GEO = ROOT / "frontend" / "public" / "geo"
RAW = ROOT / "data" / "raw"

COLOR = {
    "더불어민주당": "#152484", "국민의힘": "#E61E2B", "미래통합당": "#EF426F",
    "진보당": "#D6001C", "새로운미래": "#00B0A6", "개혁신당": "#FF7920",
    "정의당": "#FFED00", "무소속": "#888888",
}

CONF = {
    22: {
        "topo": "assembly-22.topo.json",
        "names": "assembly_22_names.json",
        "sweep": {"대구": "국민의힘", "광주": "더불어민주당", "대전": "더불어민주당",
                   "전북": "더불어민주당", "전남": "더불어민주당", "경북": "국민의힘", "제주": "더불어민주당"},
        "default": {"서울": "더불어민주당", "부산": "국민의힘", "인천": "더불어민주당", "울산": "국민의힘",
                     "경기": "더불어민주당", "강원": "국민의힘", "충북": "더불어민주당", "충남": "더불어민주당", "경남": "국민의힘"},
        "minority": {
            "서울": {"국민의힘": ["용산", "도봉갑", "마포갑", "동작을", "서초갑", "서초을", "강남갑", "강남을", "강남병", "송파갑", "송파을"]},
            "부산": {"더불어민주당": ["북구갑"]},
            "인천": {"국민의힘": ["중구강화옹진", "동구미추홀을"]},
            "울산": {"더불어민주당": ["동구"], "진보당": ["북구"]},
            "경기": {"국민의힘": ["성남분당갑", "성남분당을", "동두천양주연천을", "이천", "포천가평", "여주양평"], "개혁신당": ["화성을"]},
            "강원": {"더불어민주당": ["춘천철원화천양구을", "원주을"]},
            "충북": {"국민의힘": ["충주", "제천단양", "보은옥천영동괴산"]},
            "충남": {"국민의힘": ["보령서천", "서산태안", "홍성예산"]},
            "경남": {"더불어민주당": ["창원성산", "김해갑", "김해을"]},
        },
        "explicit": {"세종": {"세종갑": "새로운미래", "세종을": "더불어민주당"}},
        "expected": {
            "서울": {"더불어민주당": 37, "국민의힘": 11}, "부산": {"국민의힘": 17, "더불어민주당": 1},
            "대구": {"국민의힘": 12}, "인천": {"더불어민주당": 12, "국민의힘": 2}, "광주": {"더불어민주당": 8},
            "대전": {"더불어민주당": 7}, "울산": {"국민의힘": 4, "더불어민주당": 1, "진보당": 1},
            "세종": {"더불어민주당": 1, "새로운미래": 1}, "경기": {"더불어민주당": 53, "국민의힘": 6, "개혁신당": 1},
            "강원": {"국민의힘": 6, "더불어민주당": 2}, "충북": {"더불어민주당": 5, "국민의힘": 3},
            "충남": {"더불어민주당": 8, "국민의힘": 3}, "전북": {"더불어민주당": 10}, "전남": {"더불어민주당": 10},
            "경북": {"국민의힘": 13}, "경남": {"국민의힘": 13, "더불어민주당": 3}, "제주": {"더불어민주당": 3},
        },
    },
    21: {
        "topo": "assembly-21.topo.json",
        "names": "assembly_21_names.json",
        "sweep": {"광주": "더불어민주당", "대전": "더불어민주당", "세종": "더불어민주당",
                   "전남": "더불어민주당", "경북": "미래통합당", "제주": "더불어민주당"},
        "default": {"서울": "더불어민주당", "부산": "미래통합당", "대구": "미래통합당", "인천": "더불어민주당",
                     "울산": "미래통합당", "경기": "더불어민주당", "강원": "미래통합당", "충북": "더불어민주당",
                     "충남": "더불어민주당", "전북": "더불어민주당", "경남": "미래통합당"},
        "minority": {
            "서울": {"미래통합당": ["용산", "서초갑", "서초을", "강남갑", "강남을", "강남병", "송파갑", "송파을"]},
            "부산": {"더불어민주당": ["남구을", "북강서갑", "사하갑"]},
            "대구": {"무소속": ["수성을"]},
            "인천": {"미래통합당": ["중구강화옹진"], "무소속": ["동구미추홀을"]},
            "울산": {"더불어민주당": ["북구"]},
            "경기": {"미래통합당": ["성남분당갑", "평택을", "동두천연천", "용인갑", "이천", "포천가평", "여주양평"], "정의당": ["고양갑"]},
            "강원": {"더불어민주당": ["춘천철원화천양구갑", "원주갑", "원주을"], "무소속": ["강릉"]},
            "충북": {"미래통합당": ["충주", "제천단양", "보은옥천영동괴산"]},
            "충남": {"미래통합당": ["공주부여청양", "보령서천", "아산갑", "서산태안", "홍성예산"]},
            "전북": {"무소속": ["남원임실순창"]},
            "경남": {"더불어민주당": ["김해갑", "김해을", "양산을"], "무소속": ["산청함양거창합천"]},
        },
        "explicit": {},
        "expected": {
            "서울": {"더불어민주당": 41, "미래통합당": 8}, "부산": {"미래통합당": 15, "더불어민주당": 3},
            "대구": {"미래통합당": 11, "무소속": 1}, "인천": {"더불어민주당": 11, "미래통합당": 1, "무소속": 1},
            "광주": {"더불어민주당": 8}, "대전": {"더불어민주당": 7}, "울산": {"미래통합당": 5, "더불어민주당": 1},
            "세종": {"더불어민주당": 2}, "경기": {"더불어민주당": 51, "미래통합당": 7, "정의당": 1},
            "강원": {"미래통합당": 4, "더불어민주당": 3, "무소속": 1}, "충북": {"더불어민주당": 5, "미래통합당": 3},
            "충남": {"더불어민주당": 6, "미래통합당": 5}, "전북": {"더불어민주당": 9, "무소속": 1},
            "전남": {"더불어민주당": 10}, "경북": {"미래통합당": 13}, "경남": {"미래통합당": 12, "더불어민주당": 3, "무소속": 1},
            "제주": {"더불어민주당": 3},
        },
    },
}


def party_of(c, sido, sgg):
    if sido in c["sweep"]:
        return c["sweep"][sido]
    if sido in c["explicit"]:
        return c["explicit"][sido][sgg]
    for party, lst in c["minority"].get(sido, {}).items():
        if sgg in lst:
            return party
    return c["default"][sido]


def run(daesu, c):
    topo = json.loads((GEO / c["topo"]).read_text(encoding="utf-8"))
    geoms = next(iter(topo["objects"].values()))["geometries"]
    out, tally = {}, {}
    geo_sgg = {(g["properties"]["SIDO"], g["properties"]["SGG"]) for g in geoms}
    for g in geoms:
        p = g["properties"]
        party = party_of(c, p["SIDO"], p["SGG"])
        out[p["SIDO_SGG"]] = {"party": party, "color": COLOR[party]}
        tally.setdefault(p["SIDO"], Counter())[party] += 1

    ok = True
    for sido, exp in c["expected"].items():
        got = dict(tally.get(sido, {}))
        if got != exp:
            ok = False; print(f"  [{daesu}] MISMATCH {sido}: {got} != {exp}")
    for sido, m in {**c["minority"], **{k: {None: list(v)} for k, v in c["explicit"].items()}}.items():
        for _, lst in m.items():
            for sgg in lst:
                if (sido, sgg) not in geo_sgg:
                    ok = False; print(f"  [{daesu}] BAD SGG: {sido} {sgg}")

    # 당선자 이름 병합(있으면)
    nmatch = ""
    if c.get("names"):
        names = json.loads((RAW / c["names"]).read_text(encoding="utf-8"))
        miss = [k for k in out if k not in names]
        for k in out:
            out[k]["name"] = names.get(k, "")
        nmatch = f", 이름 {len(out) - len(miss)}/{len(out)}" + (f" 누락:{miss}" if miss else "")

    outp = GEO / f"assembly-{daesu}-winners.json"
    outp.write_text(json.dumps(out, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"{daesu}대: {len(out)}개 -> {outp.name}  검증 {'OK' if ok else '불일치'}{nmatch}")


def main():
    for daesu, c in CONF.items():
        run(daesu, c)


if __name__ == "__main__":
    main()
