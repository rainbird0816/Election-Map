import { ComposableMap, Geographies, Geography } from "react-simple-maps";

// 시도 TopoJSON은 런타임 로드 (컨텍스트에 올리지 않음)
const GEO_URL = "/geo/korea-sido.topo.json";
// 군위군 단독 폴리곤(경북 37310) — 2023.7 대구 편입 반영 오버레이용
const GUNWI_URL = "/geo/gunwi.geo.json";
const NO_DATA = "#E5E5E5";

// 지오파일(통계청/KOSTAT 코드) -> DB(행정표준코드) 변환
const GEO2STD = {
  "11": "11", "21": "26", "22": "27", "23": "28", "24": "29",
  "25": "30", "26": "31", "29": "36", "31": "41", "32": "42",
  "33": "43", "34": "44", "35": "45", "36": "46", "37": "47",
  "38": "48", "39": "50",
};

export default function MapKorea({ colorByCode, selectedCode, onSelect, mergeGunwi }) {
  return (
    <ComposableMap
      projection="geoMercator"
      projectionConfig={{ center: [127.8, 36.2], scale: 5500 }}
      width={520}
      height={620}
      style={{ width: "100%", height: "auto" }}
    >
      <Geographies geography={GEO_URL}>
        {({ geographies }) =>
          geographies.map((geo) => {
            const code = GEO2STD[geo.properties.code] || geo.properties.code;
            const fill = colorByCode[code] || NO_DATA;
            const isSel = code === selectedCode;
            return (
              <Geography
                key={code}
                geography={geo}
                fill={fill}
                stroke={isSel ? "#111" : "#fff"}
                strokeWidth={isSel ? 1.6 : 0.5}
                onClick={() => onSelect(code)}
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
      {/* 2023.7 군위군 대구 편입: 경북 위에 군위 폴리곤을 대구(27) 색으로 덮어 편입을 반영 */}
      {mergeGunwi && (
        <Geographies geography={GUNWI_URL}>
          {({ geographies }) =>
            geographies.map((geo) => {
              const isSel = selectedCode === "27";
              return (
                <Geography
                  key="gunwi"
                  geography={geo}
                  fill={colorByCode["27"] || NO_DATA}
                  stroke={isSel ? "#111" : "#fff"}
                  strokeWidth={isSel ? 1.4 : 0.6}
                  onClick={() => onSelect("27")}
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
      )}
    </ComposableMap>
  );
}
