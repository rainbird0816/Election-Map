import { useEffect, useState } from "react";
import { ComposableMap, Geographies, Geography } from "react-simple-maps";
import { feature } from "topojson-client";

// 국회의원 선거구 경계. geoUrl(대수별 topojson) + winners는 App이 전달.
const NO_DATA = "#E5E5E5";

const _cache = {};
async function loadFeats(url) {
  if (_cache[url]) return _cache[url];
  const topo = await fetch(url).then((r) => r.json());
  const obj = Object.values(topo.objects)[0];
  _cache[url] = feature(topo, obj).features;
  return _cache[url];
}

export default function MapDistrict({ geoUrl, winners, selectedKey, onSelect }) {
  const [feats, setFeats] = useState(null);
  useEffect(() => { setFeats(null); loadFeats(geoUrl).then(setFeats); }, [geoUrl]);

  if (!feats) return <div className="map-loading">선거구 지도 불러오는 중…</div>;
  const fc = { type: "FeatureCollection", features: feats };

  return (
    <ComposableMap
      projection="geoMercator"
      projectionConfig={{ center: [127.8, 36.2], scale: 5500 }}
      width={520}
      height={620}
      style={{ width: "100%", height: "auto" }}
    >
      <Geographies geography={fc}>
        {({ geographies }) =>
          geographies.map((g) => {
            const key = g.properties.SIDO_SGG;
            const w = winners?.[key];
            const isSel = key === selectedKey;
            return (
              <Geography
                key={g.properties.SGG_Code}
                geography={g}
                fill={w ? w.color : NO_DATA}
                stroke={isSel ? "#111" : "#fff"}
                strokeWidth={isSel ? 1.2 : 0.3}
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
