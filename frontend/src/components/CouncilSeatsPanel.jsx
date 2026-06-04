import { useEffect, useState } from "react";
import { getCouncilSeats } from "../api";
import SeatChart from "./SeatChart.jsx";

// 지방의회 구성 의석분포: level=metro(광역의원+비례)/basic(기초의원+비례)
export default function CouncilSeatsPanel({ hoecha, level, sido, sigungu, heading }) {
  const [d, setD] = useState(null);
  useEffect(() => {
    setD(null);
    if (!hoecha || !level || (!sido && !sigungu)) return;
    getCouncilSeats(hoecha, level, sido, sigungu).then(setD).catch(() => setD(null));
  }, [hoecha, level, sido, sigungu]);

  if (!d) return <p className="muted">불러오는 중…</p>;
  if (!d.total) return <p className="hint">이 지역·회차의 의석 데이터가 없습니다.</p>;
  const rows = d.parties.map((p) => ({ label: p.party, color: p.color, value: p.seats }));
  return (
    <div className="seats-panel">
      {heading !== false && (
        <h3 className="sec-title">{d.scope} {d.label} <span className="muted">총 {d.total}석</span></h3>
      )}
      {d.tie && <p className="summary-note" style={{ color: "#888" }}>제1당 동률 — 경합</p>}
      <SeatChart rows={rows} />
      <div className="mini-legend">
        {d.parties.map((p) => (
          <span key={p.party} className="legend-item">
            <span className="swatch sm" style={{ background: p.color }} />{p.party} {p.seats}
          </span>
        ))}
      </div>
    </div>
  );
}
