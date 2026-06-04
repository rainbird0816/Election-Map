# PROJECT_BRIEF — 한국 선거 결과 지도 앱 (korea-election-map) · v2 FINAL

> 민선 이후(대선 1987~ / 지선 1995~ / 총선·재보궐 포함) 선거 결과·판세를
> 지도 기반·정당색으로 한눈에 보는 로컬 실행형 웹 앱.

---

## 0. 확정된 결정사항 (LOCKED)

- **저장소: 주식 분석 앱과 별도 리포(완료).**
- **스택:** Python/FastAPI + React/Vite + SQLite. (지도용 새 의존성 추가)
- **개발 방식: 깊이 우선(depth-first).** 폭을 넓히기 전에 한 선거 흐름을 데이터→지도→지역상세까지 끝까지 관통.
- **투표소별 처리(확정):** 투표구 경계 polygon은 포기.
  - 지도 채색의 최소 단위 = **읍면동(투표구 결과를 읍면동으로 통합)**.
  - 투표구별 수치는 **표·리스트로만** 제공.
- **지역 상세 강화(확정):** 한 지역을 선택하면 그 지역의 **역대 투표 결과(추이) + 역대 당선자 목록**을 한 화면에서 확인.

---

## 1. 깊이 우선 1차 마일스톤 (정확한 정의)

> **목표 슬라이스: 전국동시지방선거 "광역단체장(시도지사)"을 시도 단위로, 가용한 모든 회차에 대해 끝까지 관통.**

이 슬라이스를 고른 이유:
- 단체장은 **행정구역 경계**를 그대로 쓴다 → 회차마다 바뀌는 **선거구 geometry 난관을 회피**(그건 총선 단계로 미룸).
- 시도는 17개뿐 → 지도/드릴다운 메커니즘을 가장 빠르게 완성.
- 같은 office(시도지사)가 여러 회차 존재 → **"역대 결과 + 역대 당선자" 기능을 곧바로 실증**.

데이터 범위(현실적 시작점):
- **3~8회(2002~2022) 광역단체장**: 동일 포맷, 공식 데이터 안정적 → 여기부터.
- 1·2회(1995·1998): 구 자료로 후속 보강.
- 9회(2026): 공식 정제본 약 2개월 시차 → 잠정/언론 집계로 "집계중" 표기 후 교체.

완성 기준(Definition of Done):
1. 3~8회 광역단체장 개표결과가 SQLite에 정규화 적재됨.
2. 최신 회차 기준 **17개 시도 choropleth**가 1위 정당색으로 채색되고, **회차 셀렉터**로 연도 전환됨.
3. 시도 클릭 → **지역 상세**: 해당 시도의 ①역대 시도지사 목록(당선자) ②회차별 1위 정당·득표율·투표율 추이.

---

## 2. 데이터 소스 (요약)

- **data.go.kr(공공데이터포털)** 중앙선관위 개표결과 CSV — 시도/구시군/읍면동/투표구 단위. 대선 16~21대, 총선 19~22대, 투·개표 조회 API는 대선13~21·총선14~22·지선3~8·보궐2010~.
- **data.nec.go.kr(국가선거정보 개방포털)** 통합 XLSX — 구 선거 보강.
- 인증키 API는 **초기 수집용으로만** 사용하고 결과는 SQLite로 동결(로컬 정적 운용).
- 경계(GeoJSON/TopoJSON): SGIS·행안부·커뮤니티 리포(시도/시군구/읍면동). 선거구 경계는 총선 단계에서 별도.
- 여론조사/예측/판세: 단일 API 없음 → nesdc.go.kr 공표자료 정제 또는 에디토리얼.

**시차 주의:** 9회 지선·2026 보궐 정제본은 검증 후 약 2개월 뒤 제공.

---

## 3. 데이터 모델 (SQLite)

```
elections        id, type(대선|총선|지선|보궐), name, hoecha_or_daesu, election_date
parties          id, name, lineage_id, color_hex, era_start, era_end
party_lineage    한나라당→새누리당→…→국민의힘 등 계보 묶음
regions          code, name, level(시도|시군구|읍면동), parent_code, valid_from, valid_to
districts        id, election_id, office, name, geo_ref          # 총선/지방의원 단계에서 사용
candidates       id, election_id, district_id, name, party_id, is_elected
results          id, election_id, level(시도|구시군|읍면동), region_code, candidate_id, votes, vote_rate
                 # 투표구 결과는 level='투표구'로 적재하되 지도엔 미사용(표 전용)
elected_seats    region_code, election_id, office, candidate_id   # "역대 당선자" 빠른 조회

# 지역 상세 가속용 precompute (역대 결과 추이)
region_election_summary
                 region_code, election_id, office,
                 winner_candidate_id, winner_party_id, winner_rate,
                 turnout, top_parties_json
```

지역 상세 핵심 쿼리:
- **역대 당선자** = `elected_seats` WHERE region_code=? ORDER BY election_date, GROUP BY office.
- **역대 결과 추이** = `region_election_summary` WHERE region_code=? ORDER BY election_date.
- 투표소(투표구) 표 = `results` WHERE level='투표구' AND 상위 읍면동=?.

---

## 4. 지도 전략 (확정)

| 단위 | 라이브러리 | 표시 |
|---|---|---|
| 시도(17) | react-simple-maps / D3 + TopoJSON | choropleth |
| 시군구(~226) | react-simple-maps / D3 | choropleth |
| 읍면동(~3,500) | MapLibre GL(벡터 타일) | choropleth(투표구 통합 결과) |
| 투표구 | (지도 X) | 표·리스트 |

채색 = 해당 단위 1위 후보의 `parties.color_hex`. 동률·접전·무투표 당선은 범례로 구분.

---

## 5. 화면 구성

- **메인(지도):** 선거 종류 탭 + 회차/연도 셀렉터 + office 토글. 시도→시군구→읍면동 드릴다운.
- **지역 상세(강화):** 상단=현재 회차 당선자 카드, 하단=**역대 당선자 목록 + 역대 득표/투표율 추이 차트**. 읍면동 선택 시 **투표구별 표** 노출.
- **선거 개관:** ①사전 예측 ②최종 여론조사 ③최종 결과 ④판세 분석.

---

## 6. 단계 (Phase)

- **P1 (1차 마일스톤):** §1 슬라이스 — 지선 광역단체장, 시도 단위, 3~8회. 데이터→시도 지도→지역상세(역대 포함)까지 관통.
- **P2:** 기초단체장 추가 → 시군구 드릴다운, 1·2·9회 보강.
- **P3:** 총선/국회의원 — 회차별 선거구 geometry(난관 구간).
- **P4:** 지방의원 + 선거 개관 4섹션.
- **P5:** 읍면동 채색(MapLibre 전환) + 투표구별 표/리스트.
- **P6:** 신규 선거 2개월 공백 동안 잠정/언론 집계 적재 경로.

---

## 7. P1 착수 순서 (난이도·토큰 최적화)

원칙 두 가지:
- **싼 토대 먼저, 무거운 UI 마지막.** 스키마·시드는 모든 걸 규정하면서 토큰이 거의 안 든다.
- **원본 데이터는 컨텍스트 금지.** CSV·TopoJSON 원본을 모델에 붙여넣지 않는다. 스크립트가 디스크에서 읽고, 모델은 헤더 몇 줄·요약만 본다. (이게 토큰 폭증의 최대 원인)

각 단계 = Claude CLI 한 세션 + 검증 가능한 산출물.

| 순서 | 단계 | 난이도 | 토큰 | 산출물 / 검증 |
|---|---|---|---|---|
| **S1** | DB 스키마 + 시드(정당·계보·시도17) | 낮음 | 낮음 | `schema.sql` 적용된 빈 DB, `parties` 조회됨 |
| **S2** | 백엔드/프론트 스캐폴딩 | 낮음 | 낮음 | `/health` 200, Vite 빈 화면 뜸 |
| **S3** | 적재 스크립트(3~8회 광역단체장 CSV) | 중간 | **주의** | `python ingest.py` 후 `results` 행수 확인 |
| **S4** | precompute 잡 | 낮음 | 낮음 | `region_election_summary`·`elected_seats` 채워짐 |
| **S5** | 읽기 API 3종 | 낮음 | 낮음 | `/elections`,`/map`,`/region/{code}/history` JSON |
| **S6** | 시도 choropleth + 회차 셀렉터 + 범례 | **높음** | **주의** | 17개 시도 정당색 채색, 연도 전환됨 |
| **S7** | 지역 상세(당선자 카드+역대 목록+추이) | 높음 | 중간 | 시도 클릭 시 역대 시도지사·추이 표시 |

토큰 절약 팁:
- **S6은 먼저 시드/목 데이터로 지도 렌더만 검증**한 뒤 S3 실데이터를 연결한다(가장 어려운 렌더링을 데이터 작업과 분리).
- TopoJSON·CSV는 `data/`에 두고 **런타임 로드**. 스크립트가 처리하며, 디버깅 시 `head`·`df.head()` 결과만 모델에 보여준다.
- 경계 파일은 시도 17개라 작지만, 읍면동(P5)부터는 반드시 벡터 타일로.

---

## 8. 리스크

1. 선거구 경계 정합성(총선·지방의원) — P3 최대 리스크.
2. 1·2회 등 구 데이터 품질.
3. 정당 계보/색상 매핑 누락 시 오해석.
4. 신규 선거 2개월 시차.

---

## 9. 시작 코드 (각 단계 스켈레톤)

> 모두 골격 + TODO. 실제 채움은 Claude CLI 세션에서. 경로는 §8(폴더 구조) 기준.

### S1 — `backend/db/schema.sql`
```sql
CREATE TABLE elections (
  id INTEGER PRIMARY KEY,
  type TEXT CHECK(type IN ('대선','총선','지선','보궐')),
  name TEXT, hoecha INTEGER, election_date TEXT
);
CREATE TABLE party_lineage (id INTEGER PRIMARY KEY, label TEXT);
CREATE TABLE parties (
  id INTEGER PRIMARY KEY, name TEXT, lineage_id INTEGER,
  color_hex TEXT, era_start TEXT, era_end TEXT,
  FOREIGN KEY(lineage_id) REFERENCES party_lineage(id)
);
CREATE TABLE regions (
  code TEXT PRIMARY KEY, name TEXT,
  level TEXT CHECK(level IN ('시도','시군구','읍면동')),
  parent_code TEXT, valid_from TEXT, valid_to TEXT
);
CREATE TABLE candidates (
  id INTEGER PRIMARY KEY, election_id INTEGER, district_id INTEGER,
  name TEXT, party_id INTEGER, is_elected INTEGER DEFAULT 0
);
CREATE TABLE results (
  id INTEGER PRIMARY KEY, election_id INTEGER,
  level TEXT CHECK(level IN ('시도','구시군','읍면동','투표구')),
  region_code TEXT, candidate_id INTEGER, votes INTEGER, vote_rate REAL
);
-- 지역 상세 가속용
CREATE TABLE elected_seats (
  region_code TEXT, election_id INTEGER, office TEXT, candidate_id INTEGER
);
CREATE TABLE region_election_summary (
  region_code TEXT, election_id INTEGER, office TEXT,
  winner_candidate_id INTEGER, winner_party_id INTEGER, winner_rate REAL,
  turnout REAL, top_parties_json TEXT
);
CREATE INDEX idx_results_lookup ON results(election_id, level, region_code);
CREATE INDEX idx_seats_region ON elected_seats(region_code);
CREATE INDEX idx_summary_region ON region_election_summary(region_code);
```

### S1 — `backend/db/seed_parties.sql` (정당 색상, 일부)
```sql
-- 2012 전후 색 반전 주의: 계보로 묶고 era별 색을 분리
INSERT INTO party_lineage(id,label) VALUES (1,'민주당계'),(2,'국민의힘계'),(3,'정의당계');
INSERT INTO parties(name,lineage_id,color_hex,era_start,era_end) VALUES
  ('더불어민주당',1,'#152484','2015-12-28',NULL),
  ('국민의힘',     2,'#E61E2B','2020-09-02',NULL),
  ('정의당',       3,'#FFED00','2013-07-21',NULL);
-- TODO: 한나라당/새누리당/자유한국당/열린우리당 등 era별 추가
```

### S3 — `backend/data_pipeline/ingest.py` (CSV는 컨텍스트 금지)
```python
"""3~8회 지선 광역단체장 개표결과 CSV -> SQLite.
원본 CSV는 data/raw/ 에 두고, 모델엔 df.head()/컬럼만 보여줄 것."""
import sqlite3, pandas as pd, pathlib

DB = "backend/db/election.sqlite"
RAW = pathlib.Path("data/raw")

def load_one(csv_path, election_id):
    df = pd.read_csv(csv_path, encoding="cp949")   # 선관위 CSV 인코딩 주의
    # TODO: 컬럼 표준화(시도명/후보/정당/득표수/득표율), 정당명 -> party_id 매핑
    # TODO: results(level='시도')로 정규화 적재, 1위 is_elected=1
    raise NotImplementedError

def main():
    con = sqlite3.connect(DB)
    # TODO: elections 행 생성(3~8회), 회차별 CSV 매핑 후 load_one 호출
    con.commit(); con.close()

if __name__ == "__main__":
    main()
```

### S4 — `backend/data_pipeline/precompute.py`
```python
"""results -> region_election_summary / elected_seats 생성."""
import sqlite3
DB = "backend/db/election.sqlite"

SUMMARY_SQL = """
INSERT INTO region_election_summary
 (region_code, election_id, office, winner_candidate_id, winner_party_id, winner_rate)
SELECT r.region_code, r.election_id, '광역단체장',
       r.candidate_id, c.party_id, r.vote_rate
FROM results r JOIN candidates c ON c.id=r.candidate_id
WHERE r.level='시도' AND c.is_elected=1;
"""
# TODO: turnout, top_parties_json 채우기 / elected_seats 동일 패턴

def main():
    con = sqlite3.connect(DB); con.executescript(SUMMARY_SQL)
    con.commit(); con.close()

if __name__ == "__main__":
    main()
```

### S5 — `backend/app/main.py`
```python
from fastapi import FastAPI
import sqlite3
app = FastAPI()
DB = "backend/db/election.sqlite"

def q(sql, args=()):
    con = sqlite3.connect(DB); con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute(sql, args)]; con.close(); return rows

@app.get("/health")
def health(): return {"ok": True}

@app.get("/elections")
def elections(): return q("SELECT * FROM elections ORDER BY election_date")

@app.get("/map")
def map_data(election_id: int):
    # 시도별 1위 정당색 -> 프론트 채색
    return q("""SELECT region_code, winner_party_id, winner_rate, p.color_hex
                FROM region_election_summary s JOIN parties p ON p.id=s.winner_party_id
                WHERE election_id=? AND office='광역단체장'""", (election_id,))

@app.get("/region/{code}/history")
def region_history(code: str):
    return {
      "winners": q("""SELECT e.name, e.election_date, c.name AS cand, c.party_id
                      FROM elected_seats s JOIN elections e ON e.id=s.election_id
                      JOIN candidates c ON c.id=s.candidate_id
                      WHERE s.region_code=? ORDER BY e.election_date""", (code,)),
      "trend":   q("""SELECT election_id, winner_party_id, winner_rate, turnout
                      FROM region_election_summary
                      WHERE region_code=? ORDER BY election_id""", (code,)),
    }
```

### S6 — `frontend/src/maps/MapKorea.jsx` (먼저 목 데이터로 렌더 검증)
```jsx
import { ComposableMap, Geographies, Geography } from "react-simple-maps";
// 시도 TopoJSON은 런타임 로드(컨텍스트에 올리지 말 것)
const GEO_URL = "/geo/korea-sido.topo.json";

export default function MapKorea({ colorByCode, onSelect }) {
  // colorByCode: { region_code: "#hex" }  (S5 /map 응답으로 구성)
  return (
    <ComposableMap projection="geoMercator"
      projectionConfig={{ center: [127.8, 36.2], scale: 5500 }}>
      <Geographies geography={GEO_URL}>
        {({ geographies }) => geographies.map((geo) => {
          const code = geo.properties.CTPRVN_CD; // TODO: 실제 코드 키 확인
          return (
            <Geography key={code} geography={geo}
              fill={colorByCode[code] || "#E5E5E5"}
              stroke="#fff"
              onClick={() => onSelect(code)}
              style={{ hover: { opacity: 0.8, cursor: "pointer" } }} />
          );
        })}
      </Geographies>
    </ComposableMap>
  );
}
```

### S7 — `frontend/src/pages/RegionDetail.jsx`
```jsx
import { useEffect, useState } from "react";
export default function RegionDetail({ code }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    if (!code) return;
    fetch(`/api/region/${code}/history`).then(r => r.json()).then(setData);
  }, [code]);
  if (!data) return null;
  return (
    <aside>
      <h2>역대 당선자</h2>
      <ul>{data.winners.map((w,i) =>
        <li key={i}>{w.election_date.slice(0,4)} · {w.cand}</li>)}</ul>
      <h2>득표·투표율 추이</h2>
      {/* TODO: recharts LineChart로 trend 시각화 (winner_rate, turnout) */}
    </aside>
  );
}
```

> 권장 착수: **S1 → S2**로 뼈대를 세우고, **S6을 목 데이터로 먼저** 띄워 지도 렌더를 검증한 뒤 **S3→S4→S5→S7**로 실데이터를 연결.
