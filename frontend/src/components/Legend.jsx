// 지도에 실제 등장한 정당색 범례 (map 응답에서 동적 구성)
export default function Legend({ mapData }) {
  const seen = new Map();
  for (const d of mapData) {
    if (d.party_name && !seen.has(d.party_name)) {
      seen.set(d.party_name, d.color_hex);
    }
  }
  if (seen.size === 0) return null;
  return (
    <div className="legend">
      {[...seen.entries()].map(([name, color]) => (
        <span key={name} className="legend-item">
          <i className="swatch" style={{ background: color }} />
          {name}
        </span>
      ))}
      <span className="legend-item">
        <i className="swatch" style={{ background: "#E5E5E5" }} />
        무자료
      </span>
    </div>
  );
}
