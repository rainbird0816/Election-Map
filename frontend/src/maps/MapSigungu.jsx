import { useEffect, useMemo, useState } from "react";
import { ComposableMap, Geographies, Geography } from "react-simple-maps";
import { geoMercator } from "d3-geo";
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

// 통합/편입 전 시기(특정 회차)에 후신 폴리곤을 폐지 기초단체로 귀속.
// election_id -> { 지오코드: { code: 기초단체코드, sido: 행정표준시도 } }
const _YG = { code: "34320", sido: "44" }; // 세종폴리곤 -> 연기군(충남)
const _CW = { code: "33049", sido: "43" }; // 청주청원구 -> 청원군(충북)
const _MS = { code: "38120", sido: "48" }; // 마산합포/마산회원 -> 마산시(경남)
const _JH = { code: "38130", sido: "48" }; // 진해구 -> 진해시(경남)
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

export default function MapSigungu({ sidoCode, electionId, colorByCode, selectedCode, onSelect }) {
  const [all, setAll] = useState(null);
  useEffect(() => { loadFeatures().then(setAll); }, []);

  // 회차별 ANNEX 반영: 폴리곤의 (소속 시도, 기초단체 코드) 해석
  const annex = ANNEX[electionId] || {};
  const sidoOf = (geo) => annex[geo.properties.code]?.sido
    ?? GEO2STD[String(geo.properties.code).slice(0, 2)];
  const codeOf = (geo) => annex[geo.properties.code]?.code
    ?? basicCode(geo.properties.code, geo.properties.name);

  const { fc, projection } = useMemo(() => {
    if (!all) return {};
    const feats = all.filter((f) => sidoOf(f) === sidoCode);
    if (!feats.length) return {};
    const fcol = { type: "FeatureCollection", features: feats };
    const proj = geoMercator().fitExtent([[12, 12], [508, 608]], fcol);
    return { fc: fcol, projection: proj };
  }, [all, sidoCode, electionId]);

  if (!fc) return <div className="map-loading">지도 불러오는 중…</div>;

  return (
    <ComposableMap projection={projection} width={520} height={620} style={{ width: "100%", height: "auto" }}>
      <Geographies geography={fc}>
        {({ geographies }) =>
          geographies.map((geo) => {
            const code = codeOf(geo);
            const isSel = code === selectedCode;
            return (
              <Geography
                key={geo.properties.code}
                geography={geo}
                fill={colorByCode[code] || NO_DATA}
                stroke={isSel ? "#111" : "#fff"}
                strokeWidth={isSel ? 1.4 : 0.5}
                onClick={() => onSelect(code, geo.properties.name)}
                style={{
                  default: { outline: "none" },
                  hover: { opacity: 0.8, cursor: "pointer", outline: "none" },
                  pressed: { outline: "none" },
                }}
              />
            );
          })
        }
      </Geographies>
    </ComposableMap>
  );
}
