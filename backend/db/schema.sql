-- korea-election-map · DB schema (P1)
-- 적용: sqlite3 election.sqlite < schema.sql  (또는 init_db.py)

PRAGMA foreign_keys = ON;

-- 선거 회차 (지선/대선/총선/보궐)
CREATE TABLE IF NOT EXISTS elections (
  id            INTEGER PRIMARY KEY,
  type          TEXT CHECK(type IN ('대선','총선','지선','보궐')),
  name          TEXT,                 -- 예: '제8회 전국동시지방선거'
  hoecha        INTEGER,              -- 회차/대수
  election_date TEXT                  -- 'YYYY-MM-DD'
);

-- 정당 계보 (한나라당→새누리당→…→국민의힘 등 묶음)
CREATE TABLE IF NOT EXISTS party_lineage (
  id    INTEGER PRIMARY KEY,
  label TEXT
);

-- 정당 (era별 색 분리: 2012 전후 색 반전 주의)
CREATE TABLE IF NOT EXISTS parties (
  id         INTEGER PRIMARY KEY,
  name       TEXT,
  lineage_id INTEGER,
  color_hex  TEXT,
  era_start  TEXT,
  era_end    TEXT,
  FOREIGN KEY(lineage_id) REFERENCES party_lineage(id)
);

-- 행정구역 (시도/시군구/읍면동)
CREATE TABLE IF NOT EXISTS regions (
  code        TEXT PRIMARY KEY,       -- 행정표준코드 (시도=2자리)
  name        TEXT,
  level       TEXT CHECK(level IN ('시도','시군구','읍면동')),
  parent_code TEXT,
  valid_from  TEXT,
  valid_to    TEXT
);

-- 선거구 (총선/지방의원 단계에서 사용; P1 미사용)
CREATE TABLE IF NOT EXISTS districts (
  id          INTEGER PRIMARY KEY,
  election_id INTEGER,
  office      TEXT,
  name        TEXT,
  geo_ref     TEXT
);

-- 후보
CREATE TABLE IF NOT EXISTS candidates (
  id          INTEGER PRIMARY KEY,
  election_id INTEGER,
  district_id INTEGER,
  office      TEXT,                   -- '광역단체장' 등 (P1 future-proof)
  region_code TEXT,                   -- 출마 지역(시도) 코드
  name        TEXT,
  party_id    INTEGER,
  is_elected  INTEGER DEFAULT 0,
  FOREIGN KEY(election_id) REFERENCES elections(id),
  FOREIGN KEY(party_id)    REFERENCES parties(id)
);

-- 개표 결과 (투표구는 level='투표구'로 적재하되 지도엔 미사용)
CREATE TABLE IF NOT EXISTS results (
  id           INTEGER PRIMARY KEY,
  election_id  INTEGER,
  level        TEXT CHECK(level IN ('시도','구시군','읍면동','투표구')),
  region_code  TEXT,
  candidate_id INTEGER,
  votes        INTEGER,
  vote_rate    REAL,
  FOREIGN KEY(election_id)  REFERENCES elections(id),
  FOREIGN KEY(candidate_id) REFERENCES candidates(id)
);

-- "역대 당선자" 빠른 조회
CREATE TABLE IF NOT EXISTS elected_seats (
  region_code  TEXT,
  election_id  INTEGER,
  office       TEXT,
  candidate_id INTEGER
);

-- 지역 상세 가속용 precompute (역대 결과 추이)
CREATE TABLE IF NOT EXISTS region_election_summary (
  region_code         TEXT,
  election_id         INTEGER,
  office              TEXT,
  winner_candidate_id INTEGER,
  winner_party_id     INTEGER,
  winner_rate         REAL,
  turnout             REAL,
  top_parties_json    TEXT
);

CREATE INDEX IF NOT EXISTS idx_results_lookup ON results(election_id, level, region_code);
CREATE INDEX IF NOT EXISTS idx_seats_region   ON elected_seats(region_code);
CREATE INDEX IF NOT EXISTS idx_summary_region ON region_election_summary(region_code);
CREATE INDEX IF NOT EXISTS idx_cand_election  ON candidates(election_id, region_code);
