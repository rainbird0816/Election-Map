import { useEffect, useMemo, useState } from "react";
import { ComposableMap, Geographies, Geography } from "react-simple-maps";
import { geoMercator } from "d3-geo";
import { feature } from "topojson-client";

// 국회의원 선거구 경계. geoUrl(대수별 topojson) + winners는 App이 전달.
// sidoFilter(축약 시도명) 지정 시 해당 시도만 보이게 자동 줌(시도 드릴다운).
const NO_DATA = "#E5E5E5";

const _cache = {};
async function loadFeats(url) {
  if (_cache[url]) return _cache[url];
  const topo = await fetch(url).then((r) => r.json());
  const obj = Object.values(topo.objects)[0];
  _cache[url] = feature(topo, obj).features;
  return _cache[url];
}

export default function MapDistrict({ geoUrl, winners, selectedKey, onSelect, sidoFilter }) {
  const [feats, setFeats] = useState(null);
  useEffect(() => { setFeats(null); loadFeats(geoUrl).then(setFeats); }, [geoUrl]);

  const { fc, projection } = useMemo(() => {
    if (!feats) return {};
    const list = sidoFilter ? feats.filter((f) => f.properties.SIDO === sidoFilter) : feats;
    if (!list.length) return {};
    const fcol = { type: "FeatureCollection", features: list };
    const proj = sidoFilter
      ? geoMercator().fitExtent([[16, 16], [504, 604]], fcol)
      : geoMercator().center([127.8, 36.2]).scale(5500).translate([260, 310]);
    return { fc: fcol, projection: proj };
  }, [feats, sidoFilter]);

  if (!fc) return <div className="map-loading">선거구 지도 불러오는 중…</div>;

  return (
    <ComposableMap projection={projection} width={520} height={620} style={{ width: "100%", height: "auto" }}>
      <Geographies geography={fc}>
        {({ geographies }) =>
          geographies.map((g) => {
            const key = g.properties.SIDO_SGG;
            const w = winners?.[key];
            const isSel = key === selectedKey;
            return (
              <Geography
                key={g.properties.SGG_Code || key}
                geography={g}
                fill={w ? w.color : NO_DATA}
                stroke={isSel ? "#111" : "#fff"}
                strokeWidth={isSel ? 1.4 : 0.4}
                onClick={() => onSelect(key, g.properties, w)}
                style={{
                  default: { outline: "none" },
                  hover: { opacity: 0.78, cursor: "pointer", outline: "none" },
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
