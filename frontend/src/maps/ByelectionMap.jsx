import { useEffect, useMemo, useState } from "react";
import { ComposableMap, Geographies, Geography } from "react-simple-maps";
import { feature } from "topojson-client";
import { geoMercator } from "d3-geo";

// 보궐 직종별 전국 채색 지도. level=sido(광역단체장·교육감) / sigungu(그 외).
const SIDO_URL = "/geo/korea-sido.topo.json";
const SIGUNGU_URL = "/geo/korea-sigungu.topo.json";
const NO_DATA = "#ECECEC";

// 지오파일(KOSTAT 2자리) → DB 행정표준 시도코드
const GEO2STD = {
  "11": "11", "21": "26", "22": "27", "23": "28", "24": "29",
  "25": "30", "26": "31", "29": "36", "31": "41", "32": "42",
  "33": "43", "34": "44", "35": "45", "36": "46", "37": "47",
  "38": "48", "39": "50",
};
// 일반구('수원시장안구') → 상위 시 코드로 합산 (MapSigungu 와 동일 규칙)
const _GU = /^(.+시).+구$/;
const basicCode = (code, name) => {
  code = String(code);
  return _GU.test(name) ? code.slice(0, 4) + "0" : code;
};

const _cache = {};
async function load(url) {
  if (_cache[url]) return _cache[url];
  const topo = await fetch(url).then((r) => r.json());
  const obj = Object.values(topo.objects)[0];
  _cache[url] = feature(topo, obj).features;
  return _cache[url];
}

export default function ByelectionMap({ level, colorByCode, selectedCode, onSelect }) {
  const [feats, setFeats] = useState(null);
  const url = level === "sido" ? SIDO_URL : SIGUNGU_URL;
  useEffect(() => { setFeats(null); load(url).then(setFeats); }, [url]);

  const projection = useMemo(() => {
    if (!feats) return null;
    return geoMercator().fitExtent([[12, 12], [508, 608]],
      { type: "FeatureCollection", features: feats });
  }, [feats]);

  if (!feats) return <div className="map-loading">지도 불러오는 중…</div>;

  const codeOf = (geo) => level === "sido"
    ? (GEO2STD[geo.properties.code] || String(geo.properties.code))
    : basicCode(geo.properties.code, geo.properties.name);

  return (
    <ComposableMap projection={projection} width={520} height={620} style={{ width: "100%", height: "auto" }}>
      <Geographies geography={{ type: "FeatureCollection", features: feats }}>
        {({ geographies }) =>
          geographies.map((geo) => {
            const code = codeOf(geo);
            const has = !!colorByCode[code];
            const isSel = code === selectedCode;
            return (
              <Geography
                key={geo.properties.code}
                geography={geo}
                fill={colorByCode[code] || NO_DATA}
                stroke={isSel ? "#111" : "#fff"}
                strokeWidth={isSel ? 1.4 : 0.4}
                onClick={() => has && onSelect(code, geo.properties.name)}
                style={{
                  default: { outline: "none" },
                  hover: { opacity: has ? 0.8 : 1, cursor: has ? "pointer" : "default", outline: "none" },
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
