import { useEffect, useState } from "react";
import { getSummary } from "../api";

// 전국 요약(선거별 평가). params로 kind/식별자 전달.
export default function SummaryPanel({ params, label }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    setData(null);
    if (!params) return;
    getSummary(params).then(setData).catch(() => setData(null));
  }, [JSON.stringify(params)]);

  if (!data || !data.rows?.length) {
    return <div className="detail empty">{label || "지역을 클릭하면 상세가 보입니다."}</div>;
  }
  const max = Math.max(...data.rows.map((r) => r.value)) || 1;
  return (
    <>
      <h2>{data.title} <span className="office-badge">전국 요약</span></h2>
      {data.note && <p className="summary-note">{data.note}</p>}
      <div className="seatbars">
        {data.rows.map((r, i) => (
          <div className="seatrow" key={i}>
            <span className="seatlabel" title={r.label}>
              <span className="swatch sm" style={{ background: r.color }} />
              {r.label}
            </span>
            <span className="seatbar"><i style={{ width: `${(r.value / max) * 100}%`, background: r.color }} /></span>
            <span className="seatnum">{r.value}{data.unit === "%" ? "%" : ""}</span>
            {r.sub && data.unit !== "%" && <span className="seatsub">{r.sub}</span>}
          </div>
        ))}
      </div>
      <p className="muted">{label}</p>
    </>
  );
}
