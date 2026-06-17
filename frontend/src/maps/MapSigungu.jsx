import { useEffect, useMemo, useState } from "react";
import { ComposableMap, Geographies, Geography, Marker } from "react-simple-maps";
import { geoMercator, geoCentroid } from "d3-geo";
import { feature } from "topojson-client";

const GEO_URL = "/geo/korea-sigungu.topo.json";
const NO_DATA = "#E5E5E5";

// 지오파일(KOSTAT 시도 2자리) -> DB 행정표준 시도 코드
const GEO2STD = {
  "11": "11", "21": "26", "22": "27", "23": "28", "24": "29",
  "25": "30", "26": "31", "29": "36", "31": "41", "32": "42",
  "33": "43", "34": "44", "35": "45", "36": "46", "37": "47",
  "38": "48", "39": "50",
};

// 일반구 합산: '수원시장안구' -> 31010(수원시). seed_sigungu.basic_code 와 동일.
const _GU = /^(.+시).+구$/;
function basicCode(code, name) {
  code = String(code);
  return _GU.test(name) ? code.slice(0, 4) + "0" : code;
}

// '수원시장안구' → 시명 '수원시' / 구명 '장안구' (일반구 도시 라벨 분리용)
const _SIGU = /^(.+시)(.+구)$/;
const siName = (name) => { const m = _SIGU.exec(name); return m ? m[1] : name; };
const guName = (name) => { const m = _SIGU.exec(name); return m ? m[2] : name; };

// 군→시 승격 연도(basicCode): 그 연도 이전 선거는 '○○군'으로 표기.
const PROMOTE_YEAR = {
  "31190": 1996, "31210": 1996, "31200": 1996, "34060": 1996, "38100": 1996, // 용인·이천·파주·논산·양산
  "31230": 1998, "31220": 1998,                                              // 김포·안성
  "31240": 2001, "31250": 2001,                                              // 화성·광주(경기)
  "31260": 2003, "31270": 2003,                                              // 양주·포천
  "34080": 2012, "31280": 2013,                                              // 당진·여주
};
const gunName = (si) => (si.endsWith("시") ? si.slice(0, -1) + "군" : si);

// 통합/편입 전 시기(특정 회차)에 후신 폴리곤을 폐지 기초단체로 귀속.
// election_id -> { 지오코드: { code: 기초단체코드, sido: 행정표준시도 } }
const _YG = { code: "34320", sido: "44", name: "연기군" }; // 세종폴리곤 -> 연기군(충남)
const _CW = { code: "33049", sido: "43", name: "청원군" }; // 청주청원구 -> 청원군(충북)
const _MS = { code: "38120", sido: "48", name: "마산시" }; // 마산합포/마산회원 -> 마산시(경남)
const _JH = { code: "38130", sido: "48", name: "진해시" }; // 진해구 -> 진해시(경남)
const ANNEX = {
  3: { "29010": _YG, "33044": _CW, "38113": _MS, "38114": _MS, "38115": _JH },
  4: { "29010": _YG, "33044": _CW, "38113": _MS, "38114": _MS, "38115": _JH },
  5: { "29010": _YG, "33044": _CW }, // 창원 통합(2010.7)은 5회 시점 완료 → 마산·진해 없음
};

let _cache = null;
async function loadFeatures() {
  if (_cache) return _cache;
  const topo = await fetch(GEO_URL).then((r) => r.json());
  const obj = Object.values(topo.objects)[0];
  _cache = feature(topo, obj).features;
  return _cache;
}

// 인천 2026-07-01 개편 자치구(검단구·영종구·제물포구 등) 합성 경계 — 9회+ 인천 드릴다운용
const INCHEON_URL = "/geo/incheon-2026.geo.json";
let _incCache = null;
async function loadIncheon() {
  if (_incCache) return _incCache;
  _incCache = (await fetch(INCHEON_URL).then((r) => r.json())).features;
  return _incCache;
}

export default function MapSigungu({ sidoCode, electionId, electionYear, colorByCode, selectedCode, onSelect, mergeGunwi, mergeSejong, mergeGyeryong, incheon2026 }) {
  const [all, setAll] = useState(null);
  const [inc, setInc] = useState(null);
  const [hovered, setHovered] = useState(null); // 마우스 올린 시군구 코드 — 나머지는 흐리게
  useEffect(() => { loadFeatures().then(setAll); }, []);
  // 인천(28) + 개편 이후 회차면 합성 경계 로드
  const useInc = incheon2026 && sidoCode === "28";
  useEffect(() => { if (useInc) loadIncheon().then(setInc); }, [useInc]);

  // 회차별 ANNEX 반영: 폴리곤의 (소속 시도, 기초단체 코드) 해석
  const annex = ANNEX[electionId] || {};
  // 2023.7 군위군(37310) 대구 편입 / 2012.7 세종 출범 이전 세종(29010)→연기군(충남) 해석
  const sidoOf = (geo) => {
    if (mergeGunwi && String(geo.properties.code) === "37310") return "27";
    if (mergeSejong && String(geo.properties.code) === "29010") return "44";
    return annex[geo.properties.code]?.sido
      ?? GEO2STD[String(geo.properties.code).slice(0, 2)];
  };
  const codeOf = (geo) => {
    if (mergeSejong && String(geo.properties.code) === "29010") return "34320";
    if (mergeGyeryong && String(geo.properties.code) === "34070") return "34060"; // 계룡→논산
    return annex[geo.properties.code]?.code
      ?? basicCode(geo.properties.code, geo.properties.name);
  };
  // 라벨용 표시명: 세종 출범 이전엔 '연기군', 계룡 출범 이전엔 '논산시', ANNEX 폐지단체는 옛 이름
  const nameOf = (geo) => {
    if (mergeSejong && String(geo.properties.code) === "29010") return "연기군";
    if (mergeGyeryong && String(geo.properties.code) === "34070") return "논산시";
    return annex[geo.properties.code]?.name ?? geo.properties.name;
  };

  const { fc, projection, groups, geoByCode } = useMemo(() => {
    if (!all) return {};
    // 인천 개편 회차: 옛 중·동·서구 대신 합성 경계(검단/영종/제물포 포함) 사용
    const feats = useInc ? inc : all.filter((f) => sidoOf(f) === sidoCode);
    if (!feats || !feats.length) return {};
    const fcol = { type: "FeatureCollection", features: feats };
    const proj = geoMercator().fitExtent([[12, 12], [508, 608]], fcol);
    // 시(기초단체) 단위로 묶음: 일반구 도시(수원시장안구 등)는 한 그룹.
    // 중심점은 미리 계산(호버 리렌더 때마다 재계산 방지).
    const gmap = new Map();
    for (const f of feats) {
      const key = codeOf(f);
      let g = gmap.get(key);
      if (!g) { g = { bcode: key, feats: [] }; gmap.set(key, g); }
      g.feats.push(f);
    }
    const grps = [];
    const byCode = {};
    for (const g of gmap.values()) {
      const isGu = g.feats.some((f) => _SIGU.test(nameOf(f))); // 일반구 도시?
      let si = isGu ? siName(nameOf(g.feats[0])) : nameOf(g.feats[0]);
      // 군→시 승격 이전 회차면 '○○군'으로 표기
      if (PROMOTE_YEAR[g.bcode] && electionYear != null && electionYear < PROMOTE_YEAR[g.bcode]) {
        si = gunName(si);
      }
      const members = g.feats.map((f) => ({
        pcode: String(f.properties.code), gu: guName(nameOf(f)), c: geoCentroid(f),
      }));
      for (const m of members) byCode[m.pcode] = g.bcode;
      const c = g.feats.length === 1 ? members[0].c
        : geoCentroid({ type: "FeatureCollection", features: g.feats });
      grps.push({ bcode: g.bcode, si, isGu, c, members });
    }
    return { fc: fcol, projection: proj, groups: grps, geoByCode: byCode };
  }, [all, inc, useInc, sidoCode, electionId, electionYear, mergeGunwi, mergeSejong, mergeGyeryong]);

  if (!fc) return <div className="map-loading">지도 불러오는 중…</div>;

  // 호버는 개별 폴리곤(구) 단위. 호버 구=또렷, 같은 시의 다른 구=중간, 그 외=흐림.
  const hoveredBcode = hovered ? geoByCode[hovered] : null;
  const dimOf = (pcode) => {
    if (!hovered) return 1;
    if (pcode === hovered) return 1;
    if (geoByCode[pcode] === hoveredBcode) return 0.55; // 같은 시의 형제 구
    return 0.2;
  };

  // 기본은 시 단위 라벨 1개. 일반구 도시를 호버하면 그 시의 구 이름들을 펼쳐 표시.
  const labelEls = [];
  for (const g of groups) {
    const isHovGroup = hoveredBcode === g.bcode;
    if (isHovGroup && g.isGu) {
      for (const m of g.members) {
        labelEls.push({ key: m.pcode, name: m.gu, c: m.c, hov: m.pcode === hovered, op: 1 });
      }
    } else {
      labelEls.push({
        key: "g" + g.bcode, name: g.si, c: g.c, hov: isHovGroup,
        op: !hovered ? 1 : isHovGroup ? 1 : 0.12,
      });
    }
  }
  const orderedLabels = hovered
    ? [...labelEls].sort((a, b) => (a.hov ? 1 : 0) - (b.hov ? 1 : 0))
    : labelEls;

  return (
    <ComposableMap projection={projection} width={520} height={620} style={{ width: "100%", height: "auto" }}>
      <Geographies geography={fc}>
        {({ geographies }) =>
          geographies.map((geo) => {
            const pcode = String(geo.properties.code);
            const code = codeOf(geo);            // 시(기초) 코드 — 채색·선택·클릭용
            const isSel = code === selectedCode;
            const op = dimOf(pcode);
            return (
              <Geography
                key={pcode}
                geography={geo}
                fill={colorByCode[code] || NO_DATA}
                stroke={isSel ? "#111" : "#fff"}
                strokeWidth={isSel ? 1.4 : 0.5}
                onClick={() => onSelect(code, geo.properties.name)}
                onMouseEnter={() => setHovered(pcode)}
                onMouseLeave={() => setHovered((h) => (h === pcode ? null : h))}
                style={{
                  default: { outline: "none", opacity: op, transition: "opacity .12s" },
                  hover: { opacity: op, cursor: "pointer", outline: "none" },
                  pressed: { opacity: op, outline: "none" },
                }}
              />
            );
          })
        }
      </Geographies>
      {/* 시군구 이름 라벨 (PC 전용 — CSS 미디어쿼리로 모바일 숨김) */}
      <g className="sgg-labels">
        {orderedLabels.map((l) => (
          <Marker key={"lbl-" + l.key} coordinates={l.c}>
            <text className={"sgg-label" + (l.hov ? " hov" : "")} textAnchor="middle" dy="0.32em"
              style={{ opacity: l.op }}>
              {l.name}
            </text>
          </Marker>
        ))}
      </g>
    </ComposableMap>
  );
}
