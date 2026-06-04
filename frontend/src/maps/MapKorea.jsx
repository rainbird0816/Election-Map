import { ComposableMap, Geographies, Geography } from "react-simple-maps";

// 시도 TopoJSON은 런타임 로드 (컨텍스트에 올리지 않음)
const GEO_URL = "/geo/korea-sido.topo.json";
const NO_DATA = "#E5E5E5";

// 지오파일(통계청/KOSTAT 코드) -> DB(행정표준코드) 변환
const GEO2STD = {
  "11": "11", "21": "26", "22": "27", "23": "28", "24": "29",
  "25": "30", "26": "31", "29": "36", "31": "41", "32": "42",
  "33": "43", "34": "44", "35": "45", "36": "46", "37": "47",
  "38": "48", "39": "50",
};

export default function MapKorea({ colorByCode, selectedCode, onSelect }) {
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
    </ComposableMap>
  );
}
