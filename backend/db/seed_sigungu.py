"""시군구 경계 TopoJSON -> 기초단체(자치단체) region 적재.

일반구 합산: 지오파일은 '수원시장안구'처럼 시를 일반구로 분할하지만,
기초단체장은 시(수원시) 단위 → 시 단위로 합산해 region 1개 생성.
  - 일반구(이름이 '○○시△△구') -> 코드 앞4자리+'0' (예: 31011→31010 수원시)
  - 그 외(자치구/군/단일시) -> 지오 코드 그대로
code = 합산 기초단체 코드, parent = 행정표준 시도 코드.
프론트 MapSigungu 의 basicCode() 와 동일 규칙.
실행: python backend/db/seed_sigungu.py
"""
import json
import re
import sqlite3
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DB = ROOT / "backend" / "db" / "election.sqlite"
GEO = ROOT / "frontend" / "public" / "geo" / "korea-sigungu.topo.json"

GEO2STD = {
    "11": "11", "21": "26", "22": "27", "23": "28", "24": "29",
    "25": "30", "26": "31", "29": "36", "31": "41", "32": "42",
    "33": "43", "34": "44", "35": "45", "36": "46", "37": "47",
    "38": "48", "39": "50",
}
_GU = re.compile(r"^(.+시).+구$")  # '수원시장안구' 등 일반구 패턴


def base_name(name):
    m = _GU.match(name)
    return m.group(1) if m else name


def basic_code(code, name):
    code = str(code)
    return code[:4] + "0" if _GU.match(name) else code


def main():
    d = json.loads(GEO.read_text(encoding="utf-8"))
    geoms = next(iter(d["objects"].values()))["geometries"]

    con = sqlite3.connect(DB)
    cur = con.cursor()
    seen = set()
    for g in geoms:
        p = g.get("properties", {})
        code = str(p.get("code"))
        bc = basic_code(code, p["name"])
        bn = base_name(p["name"])
        parent = GEO2STD.get(code[:2])
        cur.execute(
            """INSERT INTO regions(code,name,level,parent_code)
               VALUES (?,?,'시군구',?)
               ON CONFLICT(code) DO UPDATE SET name=excluded.name,
                 level='시군구', parent_code=excluded.parent_code""",
            (bc, bn, parent),
        )
        seen.add(bc)

    # 폐지된 기초단체(통합/편입 전 시기용). 지도는 후신 폴리곤에 귀속(프론트 ANNEX).
    #   연기군: 2012 세종시로 편입 (5회 충남) — 세종 폴리곤(29010)에 표시
    #   청원군: 2014 청주시와 통합 (5회 충북) — 청주청원구 폴리곤(33044)에 표시
    #   마산시·진해시: 2010 창원시로 통합 (3·4회 경남) — 창원 일반구 폴리곤에 표시
    for code, name, parent in [
        ("34320", "연기군", "44"), ("33049", "청원군", "43"),
        ("38120", "마산시", "48"), ("38130", "진해시", "48"),
    ]:
        cur.execute(
            """INSERT INTO regions(code,name,level,parent_code)
               VALUES (?,?,'시군구',?)
               ON CONFLICT(code) DO UPDATE SET name=excluded.name,
                 level='시군구', parent_code=excluded.parent_code""",
            (code, name, parent),
        )
        seen.add(code)
    con.commit()
    total = cur.execute("SELECT COUNT(*) FROM regions WHERE level='시군구'").fetchone()[0]
    gg = cur.execute("SELECT COUNT(*) FROM regions WHERE level='시군구' AND parent_code='41'").fetchone()[0]
    print(f"기초단체 regions: {total} (지오 {len(geoms)}개 -> 합산 {len(seen)}개)")
    print(f"  경기(parent=41) 기초단체 수: {gg}")
    con.close()


if __name__ == "__main__":
    main()
