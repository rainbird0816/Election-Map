import { useEffect, useState } from "react";
import { getCouncilPr } from "../api";
import SeatChart from "../components/SeatChart.jsx";

// 비례대표(광역 8/기초 9) 정당별 의석 도넛 + 당선자 명단
export default function PrDetail({ hoecha, sgtype, sido, sigungu }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    setData(null);
    if (!hoecha || !sgtype || (!sido && !sigungu)) return;
    getCouncilPr(hoecha, sgtype, sido, sigungu).then(setData).catch(() => setData(null));
  }, [hoecha, sgtype, sido, sigungu]);

  if (!data) return <aside className="detail"><p className="muted">불러오는 중…</p></aside>;
  if (!data.total) {
    return <aside className="detail"><h2>{data.scope}</h2>
      <p className="hint">이 회차·지역의 {data.label} 데이터가 없습니다(기초비례는 4회부터).</p></aside>;
  }
  const rows = data.parties.map((p) => ({ label: p.party, color: p.color, value: p.seats }));
  return (
    <aside className="detail">
      <h2>{data.scope} {data.label} <span className="office-badge">총 {data.total}석</span></h2>
      <SeatChart rows={rows} />
      {data.parties.map((p) => (
        <div key={p.party} className="pr-party">
          <div className="pr-party-head">
            <span className="dot" style={{ background: p.color }} />
            <b>{p.party}</b> <span className="muted">{p.seats}석</span>
          </div>
          <div className="pr-names">{p.names.join(", ")}</div>
        </div>
      ))}
      <p className="muted">비례대표 당선자 · 중앙선관위. 정당 득표율 비례배분.</p>
    </aside>
  );
}
