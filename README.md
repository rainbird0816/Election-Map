# korea-election-map

민선 이후 한국 선거 결과를 지도·정당색으로 보는 로컬 웹 앱.
- **P1 완료**: 광역단체장(시도지사) 3~8회(2002~2022), 시도 choropleth + 역대/추이. 후보 전원(낙선 포함) 358명 — 선관위 OpenAPI(개표결과 type3)로 정확 득표/득표율 보강(`ingest_local_nec.py`). 투표율은 공식 선관위 값 유지(precompute가 `metro_governors.json`에서 별도 로드).
- **P2 완료**: 기초단체장 시군구 드릴다운 (시도 클릭 → 시군구 지도 자동 줌 → 구 상세). **일반구 합산**(성남=수정/중원/분당 → 성남시). **전국 3~8회** 적재. 기초단체장 1,366석 + **후보 전원(낙선 포함) 4,345명·정확 득표/득표율** — 선관위 OpenAPI(개표결과 type4)로 보강(`ingest_local_nec.py`, ingest_local 위키 위에 회차·시군구별 교체). 3회 2곳만 통합-전 시군이라 위키 유지.
- **P3 진행**: 총선(국회의원). **선거종류 탭(지방선거/국회의원)**. ① 시도 단위 집계(**13~22대**, 옛 정당색·미존재 시도 회색) — 시도를 지역구 의석 최다 정당색으로 채색. ② **선거구 경계 지도(21·22대)** — 21대 253 / 22대 254 소선거구 polygon을 당선 정당색으로 채색(서브탭 '지역구 경계', 대수 전환). 선거구 클릭 시 **당선자 이름 + 정당**(21대 253 + 22대 254 전원). 원본: OhmyNews 선거구 GeoJSON → mapshaper topojson 변환(winding 정규화), 당선자 이름은 `data/raw/assembly_{21,22}_names.json`. ③ **선거구 상세: 후보 전원(낙선 포함)·투표구별 득표**(21·22대) — 선관위 개방포털 개표결과 Excel(`data.nec.go.kr/file-download.do`, 무인증)에서 투표구별·후보별 적재. 선거구 클릭 시 후보별 득표/득표율 표 + 투표구별(거소·관외·국외·관내사전·일반투표구) 펼침 표.
- **P4 지방의원(3~8회)**: 지방선거 탭 내 서브탭 '지방의원' → 광역의원(시·도의원)/기초의원(구·시·군의원) 토글. 시도 choropleth(의석 최다 정당색) → 시군구 드릴다운 → **선거구별 후보 전원(낙선 포함)·득표·당선** 표. 광역·기초의원 3~8회 **시군구 100% 매칭(미매칭 0)**, 회차별 당선자 정합(무투표당선 포함), 당선 정당색 100%. 출처: 선관위 OpenAPI(개표결과 getXmntckSttusInfoInqire + 당선인). 선거구 단위(투표구별 아님). 키: `backend/.secrets/nec_key.txt`.
- **교육감(P4 일부)**: 지방선거 탭 내 서브탭 '교육감'. 시도를 **성향(진보/보수/중도)색**으로 채색, 클릭 시 교육감 이름·성향·역대 교육감. **5·6·7·8회** 적재. `data/raw/superintendents.json`.
- **대선(대통령)**: 선거종류 탭 '대통령'. **16~21대(2002~2025)**. 시도 choropleth(1위 후보 정당색) → 시군구 드릴다운(일반구는 시로 합산) → **후보 전원(낙선 포함)·득표·득표율 + 투표구별 + 역대 대선 1위**. 출처: 선관위 개방포털 개표결과 Excel(`data.nec.go.kr/file-download.do`, 무인증, 투표구별). `ingest_president.py` → `pres_cand/pres_region/pres_precinct` 테이블 + `/president/*` API. 투표구 101,088행.

## 구성

```
backend/
  db/        schema.sql, seed_parties.sql, seed_regions.sql, init_db.py,
             seed_sigungu.py(지오파일→250 시군구 region), election.sqlite
  data_pipeline/  ingest.py(광역), ingest_local.py(기초), precompute.py(요약, 광역+기초)
  app/main.py     FastAPI 읽기 API (/map 은 office·parent 파라미터 지원)
  .venv/          파이썬 가상환경
frontend/    Vite + React (react-simple-maps + d3-geo fitExtent 드릴다운, recharts 추이)
  public/geo/  korea-sido.topo.json, korea-sigungu.topo.json
data/raw/    metro_governors.json(광역), local_mayors.json(기초)  (웹 수집 원본)
```

## 최초 1회 셋업

```powershell
# 백엔드
python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
$V = "backend/.venv/Scripts/python.exe"
& $V backend/db/init_db.py                       # 스키마+시드(정당·시도) -> election.sqlite
& $V backend/db/seed_sigungu.py                  # 250 시군구 region (지오파일 기반)
& $V backend/data_pipeline/ingest.py             # 광역단체장 적재
& $V backend/data_pipeline/ingest_local.py       # 기초단체장 적재(위키 기반)
& $V backend/data_pipeline/ingest_local_nec.py   # 기초단체장 낙선자 보강(선관위 OpenAPI, 키 필요)
& $V backend/data_pipeline/precompute.py         # 요약/역대 생성(광역+기초)
& $V backend/data_pipeline/ingest_assembly.py    # 총선(국회의원) 시도별 의석 — precompute 다음에
& $V backend/data_pipeline/ingest_superintendent.py  # 교육감(시도·성향) — precompute 다음에
& $V backend/data_pipeline/gen_assembly_districts.py  # 선거구 winners(정당+당선자명) 생성
& $V backend/data_pipeline/ingest_assembly_precinct.py 22  # 총선 투표구별·낙선자(22대) — Excel 필요
& $V backend/data_pipeline/ingest_assembly_precinct.py 21  # 총선 투표구별·낙선자(21대)
# 지방의원 3~8회(광역·기초) — OpenAPI 키 필요. sgId: 3회20020613 4회20060531 5회20100602 6회20140604 7회20180613 8회20220601
& $V backend/data_pipeline/ingest_council.py 20220601
& $V backend/data_pipeline/ingest_president.py    # 대선 16~21대(개표결과 Excel 자동 다운로드, 무인증)

# 프론트
cd frontend && npm install
```

## 실행 (개발)

```powershell
# 터미널 1 — 백엔드 (backend/ 에서)
.venv/Scripts/python.exe -m uvicorn app.main:app --port 8000

# 터미널 2 — 프론트 (frontend/ 에서)
npm run dev      # http://localhost:5173  (/api -> :8000 프록시, rewrite 없음)
```

## 배포 A — Git + Vercel (권장: URL 즉시)
프론트는 Vercel 정적 호스팅, `/api/*` 는 FastAPI 서버리스 함수(`api/index.py`)로 rewrite, SQLite는 함수에 동봉(`vercel.json`의 includeFiles). 설정 파일 이미 포함.
```bash
# 1) GitHub 저장소에 푸시
git remote add origin https://github.com/<user>/korea-election-map.git
git push -u origin master
# 2) vercel.com → Add New Project → 이 저장소 Import → (설정 자동 인식) Deploy
#    또는 CLI:  npm i -g vercel && vercel --prod
```
- `vercel.json`이 빌드(`frontend` Vite)·출력(`frontend/dist`)·`/api` 라우팅·DB 동봉을 자동 구성. 추가 설정 불필요.
- DB(`backend/db/election.sqlite`)는 git에 커밋되어 있어야 함(이미 커밋). 원본 Excel/PDF·API키는 `.gitignore` 제외.

## 배포 B — 단일 Docker 컨테이너
FastAPI가 `/api/*`(API)와 빌드된 프론트 정적파일을 함께 서빙. SQLite(읽기전용) 동봉.
```bash
docker build -t korea-election .
docker run -p 8000:8000 korea-election     # http://localhost:8000
```
- 멀티스테이지(node로 프론트 빌드 → python 런타임). 런타임 의존성은 fastapi+uvicorn만.
- Railway/Render/Fly/any VPS에 이 Dockerfile 하나로 배포(포트 8000). CORS 불필요(동일 출처).
- `.dockerignore`가 `.venv`/`node_modules`/`data/raw`/`backend/.secrets`(API키) 제외.
- DB 재생성 없이 동봉된 `backend/db/election.sqlite`(약 21MB)로 바로 구동.

## 기능 요약(탭)
- **지방선거**: 단체장(광역/기초·낙선 전원)·교육감(성향)·지방의원(광역/기초·선거구별 낙선 전원)
- **국회의원**: 시도집계(13~22대) + 선거구 경계지도(21·22대, 투표구별·낙선 전원)
- **대통령**: 16~21대 시도→시군구 드릴다운, 후보 전원·투표구별·**역대 진영별 득표율 추이 차트**
- **투표소 조회**: 대선 시도→시군구 선택 후 **투표구/읍면동별** 후보 전원 득표 표
- 각 선거 전국 화면엔 **전국 요약(평가)** 패널(1위·격차/의석분포/성향분포)

## API (`/api` 프리픽스)
- `GET /api/elections`, `GET /api/map?election_id=&office=&parent=`
- `GET /api/region/{code}/history|results`
- `GET /api/council/map|detail`, `GET /api/president/map|region|history|national|elections`
- `GET /api/summary?kind=president|assembly|local|council|superintendent&...` — 전국 요약
- `GET /api/precinct/lookup?daesu=&sigungu_code=&mode=투표구|읍면동` — 투표소/읍면동 종합

## 데이터 출처 / 주의 / 후속(TODO)
- **후보**: 3~8회 **전체 후보(낙선 포함, 총 358명)**. 4~8회는 '제N회…광역자치단체장' 문서, 3회는 시도별 직책 문서(`○○시장/도지사 선거`)에서 — 모두 중앙선관위 개표결과 전재.
- **투표율**: 중앙선관위 공식 — 『제6회 투표율 분석』 표2(6회 실제)·표3(4·5·6회 실제 시도별), 7·8회 선관위 시도별 투표율. **전 회차·전 시도 채움(99/99).** (원본 PDF: `data/raw/nec_6th_turnout.pdf`)
- 정당: 군소정당은 `ingest.py`가 자동 등록(lineage 7 '기타', 색상 `MINOR_COLORS`).
- 코드 체계: DB는 행정표준코드(부산 26, 세종 36…), 지오파일은 통계청 코드(부산 21…) → `MapKorea.jsx`의 `GEO2STD`에서 변환.
- **기초단체장(P2)**: 전국 15개 시도 5~8회(광역시7+경기+강원·충북·충남·전북·전남·경북·경남). 광역시7·경기는 당선자+2위, 7개 도는 당선자만. 무투표 rate=100. 출처: 위키백과 '제N회…○○'.
- **일반구 합산**: '수원시장안구'→시 단위 합산(코드 앞4자리+'0', 예 31011→31010 수원시). `seed_sigungu.py basic_code()` ↔ 프론트 `MapSigungu.basicCode()` 동일. 광역시 자치구엔 무영향.
- **세종/통합 특례**: 통합·편입 전 폐지 기초단체를 후신 폴리곤에 회차별 귀속(`MapSigungu.ANNEX`): 연기군(충남,3~5회=세종폴리곤), 청원군(충북,3~5회=청주청원구), 마산시·진해시(경남,3~4회=창원 마산합포/마산회원/진해구). 별칭(승격): `SIGUNGU_ALIAS` (남구→미추홀구, 여주군/당진군/양주군/포천군→시). 3회엔 계룡시·증평군 미존재(2003 신설).
- TODO: 도 7곳 2위·군소후보(현재 당선자만), 광역시7+경기만 2위 보유. (제주는 2006부터 단층이라 기초단체장 없음)
- TODO: 1·2회(1995·1998)·9회(2026) 보강. (3~8회 광역단체장은 후보·투표율 완비)
