-- 시도 17개 (행정표준코드 2자리; GeoJSON CTPRVN_CD와 일치)
-- 세종(36)은 2012-07-01 출범 → 6회(2014)부터 등장. valid_from으로 표기.

INSERT OR IGNORE INTO regions(code,name,level,parent_code,valid_from,valid_to) VALUES
  ('11','서울특별시',      '시도',NULL,NULL,NULL),
  ('26','부산광역시',      '시도',NULL,NULL,NULL),
  ('27','대구광역시',      '시도',NULL,NULL,NULL),
  ('28','인천광역시',      '시도',NULL,NULL,NULL),
  ('29','광주광역시',      '시도',NULL,NULL,NULL),
  ('30','대전광역시',      '시도',NULL,NULL,NULL),
  ('31','울산광역시',      '시도',NULL,NULL,NULL),
  ('36','세종특별자치시',  '시도',NULL,'2012-07-01',NULL),
  ('41','경기도',          '시도',NULL,NULL,NULL),
  ('42','강원도',          '시도',NULL,NULL,NULL),
  ('43','충청북도',        '시도',NULL,NULL,NULL),
  ('44','충청남도',        '시도',NULL,NULL,NULL),
  ('45','전라북도',        '시도',NULL,NULL,NULL),
  ('46','전라남도',        '시도',NULL,NULL,NULL),
  ('47','경상북도',        '시도',NULL,NULL,NULL),
  ('48','경상남도',        '시도',NULL,NULL,NULL),
  ('50','제주특별자치도',  '시도',NULL,NULL,NULL),
  -- 광주(29)+전남(46) 통합. 2026-07-01 출범 예정 → 9회(2026)부터 등장.
  -- 행정표준코드 미확정이라 임시 '49'(현재 미사용 시도코드) 사용. 지도 경계는 29+46 합성.
  ('49','전남광주통합특별시','시도',NULL,'2026-07-01',NULL);
