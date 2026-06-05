import { useEffect, useState } from "react";
import { getMap } from "../api";

// 기초 종합 시도 모드: 그 시도 내 기초단체장 정당 분포 + 안내. (기초 클릭 시 SigunguDashboard 로 전환)
export default function BasicDashboard({ hoecha, sidoCode, sidoName }) {
  const [rows, setRows] = useState(null);
  useEffect(() => {
    setRows(null);
    if (!hoecha || !sidoCode) return;
    getMap(hoecha, "기초단체장", sidoCode).then(setRows).catch(() => setRows([]));
  }, [hoecha, sidoCode]);

  const tally = {};
  for (const r of rows || []) {
    const k = r.party_name || "기타";
    (tally[k] || (tally[k] = { n: 0, color: r.color_hex })).n++;
  }
  const list = Object.entries(tally).sort((a, b) => b[1].n - a[1].n);
  const total = (rows || []).length;

  return (
    <aside className="detail">
      <h2>{sidoName} <span className="office-badge">기초 종합</span></h2>
      <h3 className="sec-title">기초단체장 정당 분포 <span className="muted">({total}개 시·군·구)</span></h3>
      {list.length ? (
        <div className="mini-legend">
          {list.map(([p, v]) => (
            <span key={p} className="legend-item">
              <span className="swatch sm" style={{ background: v.color || "#bbb" }} />{p} {v.n}
            </span>
          ))}
        </div>
      ) : <p className="muted">데이터 없음</p>}
      <p className="muted">시·군·구를 클릭하면 그 기초의 기초단체장·기초의회·기초의원·기초비례 종합이 보입니다.</p>
    </aside>
  );
}
