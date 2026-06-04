import { useEffect, useMemo, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, Legend as RLegend, ResponsiveContainer, CartesianGrid,
} from "recharts";
import { getOverview } from "../api";

const KINDS = [
  { key: "assembly", label: "국회의원" },
  { key: "local", label: "단체장", office: "광역단체장" },
  { key: "council", label: "지방의원", sgtype: 5 },
  { key: "president", label: "대통령" },
];

export default function OverviewPage() {
  const [kind, setKind] = useState("assembly");
  const [sgtype, setSgtype] = useState(5);
  const [office, setOffice] = useState("광역단체장");
  const [data, setData] = useState(null);
  const [sel, setSel] = useState(null); // 선택 회차 index

  useEffect(() => {
    setData(null); setSel(null);
    const params = { kind };
    if (kind === "council") params.sgtype = sgtype;
    if (kind === "local") params.office = office;
    getOverview(params).then((d) => { setData(d); setSel(d.series.length - 1); }).catch(() => setData(null));
  }, [kind, sgtype, office]);

  const series = data?.series || [];
  const unit = data?.unit || "석";
  const cur = sel != null ? series[sel] : null;
  const prev = sel != null && sel > 0 ? series[sel - 1] : null;

  // 추이 차트: 회차별 정당값 + 주요 정당(어느 회차든 top4) 라인
  const { chartData, topParties, colorOf } = useMemo(() => {
    const colorOf = {};
    const top = new Set();
    const chartData = series.map((s) => {
      const row = { label: s.label, year: s.year };
      s.parties.forEach((p) => { row[p.party] = p.seats; colorOf[p.party] = p.color; });
      s.parties.slice(0, 4).forEach((p) => top.add(p.party));
      return row;
    });
    return { chartData, topParties: [...top], colorOf };
  }, [series]);

  const deltas = useMemo(() => {
    if (!cur) return [];
    const pmap = {};
    (prev?.parties || []).forEach((p) => { pmap[p.party] = p.seats; });
    return cur.parties.map((p) => ({ ...p, delta: prev ? p.seats - (pmap[p.party] || 0) : null }));
  }, [cur, prev]);

  return (
    <div className="lookup-page overview">
      <h2>선거 개관 <span className="muted">(데이터 사실 분석)</span></h2>
      <div className="lookup-controls">
        <div className="seg">
          {KINDS.map((k) => (
            <button key={k.key} className={`seg-btn ${kind === k.key ? "active" : ""}`} onClick={() => setKind(k.key)}>{k.label}</button>
          ))}
        </div>
        {kind === "council" && (
          <div className="seg">
            {[[5, "광역의원"], [6, "기초의원"], [8, "광역비례"], [9, "기초비례"]].map(([v, l]) => (
              <button key={v} className={`seg-btn ${sgtype === v ? "active" : ""}`} onClick={() => setSgtype(v)}>{l}</button>
            ))}
          </div>
        )}
        {kind === "local" && (
          <div className="seg">
            {["광역단체장", "기초단체장"].map((o) => (
              <button key={o} className={`seg-btn ${office === o ? "active" : ""}`} onClick={() => setOffice(o)}>{o}</button>
            ))}
          </div>
        )}
        {series.length > 0 && (
          <label>기준 회차
            <select value={sel ?? ""} onChange={(e) => setSel(Number(e.target.value))}>
              {series.map((s, i) => <option key={s.id} value={i}>{s.label} ({s.year})</option>)}
            </select>
          </label>
        )}
      </div>

      {!data ? <p className="muted">불러오는 중…</p> : !cur ? <p className="hint">데이터가 없습니다.</p> : (
        <div className="overview-grid">
          <section className="ov-card">
            <h3 className="sec-title">{cur.label} ({cur.year}) 결과</h3>
            <div className="ov-headline">
              <span className="dot" style={{ background: cur.parties[0].color }} />
              <b>{cur.parties[0].party}</b> {kind === "president" ? "득표 1위" : "제1당"} · {cur.parties[0].seats}{unit}
              {cur.parties[1] && <span className="muted"> (2위 {cur.parties[1].party} {cur.parties[1].seats}{unit}, 격차 {(cur.parties[0].seats - cur.parties[1].seats).toFixed(unit === "%" ? 1 : 0)}{unit})</span>}
            </div>
            <table className="cand-table ov-table">
              <thead><tr><th></th><th>정당</th><th className="num">{unit === "%" ? "득표율" : unit}</th><th className="num">직전 대비</th></tr></thead>
              <tbody>
                {deltas.map((p) => (
                  <tr key={p.party}>
                    <td><span className="dot" style={{ background: p.color }} /></td>
                    <td>{p.party}</td>
                    <td className="num">{p.seats}{unit === "%" ? "%" : ""}</td>
                    <td className={"num " + (p.delta > 0 ? "up" : p.delta < 0 ? "down" : "")}>
                      {p.delta == null ? "—" : p.delta > 0 ? `▲${p.delta}` : p.delta < 0 ? `▼${-p.delta}` : "0"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section className="ov-card">
            <h3 className="sec-title">정당별 {unit === "%" ? "득표율" : "의석"} 추이</h3>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={chartData} margin={{ top: 5, right: 12, bottom: 0, left: -12 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                <XAxis dataKey="year" fontSize={11} /><YAxis fontSize={11} unit={unit === "%" ? "%" : ""} />
                <Tooltip formatter={(v) => `${v}${unit === "%" ? "%" : unit}`} />
                <RLegend wrapperStyle={{ fontSize: 12 }} />
                {topParties.map((p) => (
                  <Line key={p} type="monotone" dataKey={p} name={p} stroke={colorOf[p]} strokeWidth={2} dot={{ r: 2 }} connectNulls />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </section>
        </div>
      )}
      <p className="muted">중앙선관위 개표결과 기반. 객관 지표(의석·득표·증감)만 표시합니다.</p>
    </div>
  );
}
