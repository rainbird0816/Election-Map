import { useEffect, useMemo, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, Legend as RLegend, ResponsiveContainer, CartesianGrid,
} from "recharts";
import { getOverview } from "../api";

const KINDS = [
  { key: "president", label: "대통령" },
  { key: "assembly", label: "국회의원" },
  { key: "local", label: "단체장", office: "광역단체장" },
  { key: "council", label: "지방의원", sgtype: 5 },
];

// 데이터에서 도출되는 판단(객관 지표 기반 해석)
function buildInsights(series, unit, group) {
  if (!series || series.length < 2) return [];
  const isPct = unit === "%";
  const ent = group === "lineage" ? "세력" : (isPct ? "세력" : "당");
  const totalOf = (s) => s.parties.reduce((a, p) => a + p.seats, 0);
  const out = [];

  const winners = series.map((s) => s.parties[0].party);
  let changes = 0;
  for (let i = 1; i < winners.length; i++) if (winners[i] !== winners[i - 1]) changes++;
  const span = `${series[0].label}~${series[series.length - 1].label}`;
  out.push(`${span} ${series.length}번의 선거에서 1위 ${ent}이(가) ${changes}번 교체됐습니다${changes === 0 ? " — 줄곧 한 세력이 우위" : ""}.`);

  let best = 1, cur = 1, bestP = winners[0];
  for (let i = 1; i < winners.length; i++) {
    if (winners[i] === winners[i - 1]) { cur++; if (cur > best) { best = cur; bestP = winners[i]; } } else cur = 1;
  }
  if (best >= 2) out.push(`최장 연속 1위는 ${bestP}로 ${best}회 연속입니다.`);

  const last = series[series.length - 1];
  const top = last.parties[0].party;
  const seq = series.slice(-3).map((s) => { const f = s.parties.find((p) => p.party === top); return f ? f.seats : 0; });
  if (seq.length >= 2) {
    const d = seq[seq.length - 1] - seq[0];
    const dir = d > 0 ? "상승" : d < 0 ? "하락" : "보합";
    out.push(`${top}의 최근 ${seq.length}회 ${isPct ? "득표율" : "의석"}은 ${seq.join(" → ")}${isPct ? "%" : unit}로 ${dir} 추세입니다.`);
  }

  const conc = (s) => {
    const t = totalOf(s) || 1;
    const top2 = (s.parties[0]?.seats || 0) + (s.parties[1]?.seats || 0);
    return (top2 / t) * 100;
  };
  const c0 = conc(series[0]), c1 = conc(last), dc = c1 - c0;
  out.push(`상위 2${ent} 집중도는 ${series[0].label} ${c0.toFixed(0)}% → ${last.label} ${c1.toFixed(0)}%로 ${Math.abs(dc) < 3 ? "비슷합니다" : dc > 0 ? "심화(양극화)됐습니다" : "완화됐습니다"}.`);
  return out;
}

export default function OverviewPage() {
  const [kind, setKind] = useState("president");
  const [sgtype, setSgtype] = useState(5);
  const [office, setOffice] = useState("광역단체장");
  const [group, setGroup] = useState("lineage"); // lineage 계열별 / party 개별정당
  const [data, setData] = useState(null);
  const [sel, setSel] = useState(null); // 선택 회차 index

  useEffect(() => {
    setData(null); setSel(null);
    const params = { kind, group };
    if (kind === "council") params.sgtype = sgtype;
    if (kind === "local") params.office = office;
    getOverview(params).then((d) => { setData(d); setSel(d.series.length - 1); }).catch(() => setData(null));
  }, [kind, sgtype, office, group]);

  const series = data?.series || [];
  const unit = data?.unit || "석";
  const cur = sel != null ? series[sel] : null;
  const prev = sel != null && sel > 0 ? series[sel - 1] : null;

  // 추이 차트: 회차별 값 + 주요(어느 회차든 top4) 라인
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
    return cur.parties.map((p) => ({ ...p, delta: prev ? +(p.seats - (pmap[p.party] || 0)).toFixed(unit === "%" ? 1 : 0) : null }));
  }, [cur, prev, unit]);

  const insights = useMemo(() => buildInsights(series, unit, group), [series, unit, group]);
  const entWord = group === "lineage" ? "세력" : (unit === "%" ? "세력" : "당");

  return (
    <div className="lookup-page overview">
      <h2>선거 개관 <span className="muted">(데이터 사실 분석 · 계열 분류)</span></h2>
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
        <div className="seg">
          {[["lineage", "계열별"], ["party", "개별 정당별"]].map(([v, l]) => (
            <button key={v} className={`seg-btn ${group === v ? "active" : ""}`} onClick={() => setGroup(v)}>{l}</button>
          ))}
        </div>
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
              <b>{cur.parties[0].party}</b> {kind === "president" ? "득표 1위" : `제1${entWord}`} · {cur.parties[0].seats}{unit}
              {cur.parties[1] && <span className="muted"> (2위 {cur.parties[1].party} {cur.parties[1].seats}{unit}, 격차 {(cur.parties[0].seats - cur.parties[1].seats).toFixed(unit === "%" ? 1 : 0)}{unit})</span>}
            </div>
            <table className="cand-table ov-table">
              <thead><tr><th></th><th>{group === "lineage" ? "계열" : "정당"}</th><th className="num">{unit === "%" ? "득표율" : unit}</th><th className="num">직전 대비</th></tr></thead>
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
            <h3 className="sec-title">{group === "lineage" ? "계열별" : "정당별"} {unit === "%" ? "득표율" : "의석"} 추이</h3>
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

          {insights.length > 0 && (
            <section className="ov-card ov-insight">
              <h3 className="sec-title">데이터 판단 <span className="muted">(지표에서 도출)</span></h3>
              <ul className="insight-list">
                {insights.map((t, i) => <li key={i}>{t}</li>)}
              </ul>
            </section>
          )}
        </div>
      )}
      <p className="muted">
        중앙선관위 개표결과 기반. ‘계열별’은 이름을 바꾸거나 합당·분당한 정당을 같은 정치 계열로 묶어 집계합니다
        (예: 민정당→민자당→신한국당→한나라당→…→국민의힘, 평민당→국민회의→…→더불어민주당).
        판단은 의석·득표·증감 등 객관 지표에서 자동 도출한 해석입니다.
        13~15대 대선(1987~1997)은 시도 단위만 보유하며 3김 시대 정당은 후신 정당 기준으로 분류했습니다.
      </p>
    </div>
  );
}
