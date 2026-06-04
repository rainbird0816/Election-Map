import { useEffect, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer, Legend as RLegend,
} from "recharts";
import { getRegionHistory, getRegionResults } from "../api";

export default function RegionDetail({ code, electionId, office = "광역단체장" }) {
  const [hist, setHist] = useState(null);
  const [results, setResults] = useState([]);

  useEffect(() => {
    if (!code) return;
    setHist(null);
    setResults([]);
    getRegionHistory(code, office).then(setHist).catch(() => setHist(null));
  }, [code, office]);

  useEffect(() => {
    if (!code || !electionId) return;
    getRegionResults(code, electionId).then(setResults).catch(() => setResults([]));
  }, [code, electionId]);

  if (!code) return <aside className="detail empty">지역을 클릭하세요.</aside>;
  if (!hist) return <aside className="detail">불러오는 중…</aside>;

  // 교육감: 성향 + 역대 교육감
  if (office === "교육감") {
    const parse = (t) => { try { return JSON.parse(t.top_parties_json)[0] || {}; } catch { return {}; } };
    const cur = hist.trend.find((t) => t.election_id === electionId);
    const c = cur ? parse(cur) : {};
    return (
      <aside className="detail">
        <h2>{hist.region.name} <span className="office-badge">교육감</span></h2>
        {cur ? (
          <div className="winner-card" style={{ borderLeftColor: c.color }}>
            <div className="wc-label">교육감 당선자</div>
            <div className="wc-name">{c.name}</div>
            <div className="wc-party" style={{ color: c.color }}>{c.lean} 성향</div>
          </div>
        ) : <p className="muted">이 회차 교육감 데이터 없음(6~8회 적재).</p>}
        <h3>역대 교육감</h3>
        <ul className="winners-list">
          {hist.trend.map((t) => { const w = parse(t); return (
            <li key={t.election_id}>
              <span className="yr">{t.election_date?.slice(0, 4)}</span>
              <i className="swatch sm" style={{ background: w.color }} />
              <span>{w.name}</span>
              <span className="party">{w.lean}</span>
            </li>
          ); })}
          {hist.trend.length === 0 && <li className="muted">데이터 없음</li>}
        </ul>
      </aside>
    );
  }

  // 국회의원(총선): 지역구 의석 분포
  if (office === "국회의원") {
    const cur = hist.trend.find((t) => t.election_id === electionId);
    let seats = [];
    try { seats = cur ? JSON.parse(cur.top_parties_json) : []; } catch { seats = []; }
    const total = seats.reduce((s, x) => s + x.seats, 0);
    return (
      <aside className="detail">
        <h2>{hist.region.name} <span className="office-badge">국회의원</span></h2>
        <div className="wc-label">지역구 의석 (총 {total}석)</div>
        <div className="seatbars">
          {seats.map((s) => (
            <div key={s.party} className="seatrow">
              <span className="seatlabel"><i className="swatch sm" style={{ background: s.color }} />{s.party}</span>
              <span className="seatbar"><i style={{ width: `${total ? (s.seats / total) * 100 : 0}%`, background: s.color }} /></span>
              <span className="seatnum">{s.seats}</span>
            </div>
          ))}
          {seats.length === 0 && <p className="muted">데이터 없음</p>}
        </div>
        <h3>역대 제1당 (지역구)</h3>
        <ul className="winners-list">
          {hist.trend.map((t) => {
            let tot = 0;
            try { tot = JSON.parse(t.top_parties_json).reduce((a, x) => a + x.seats, 0); } catch {}
            return (
              <li key={t.election_id}>
                <span className="yr">{t.election_date?.slice(0, 4)}</span>
                <i className="swatch sm" style={{ background: t.color_hex }} />
                <span>{t.party_name}</span>
                <span className="party">{tot}석 중 최다</span>
              </li>
            );
          })}
        </ul>
      </aside>
    );
  }

  const trend = hist.trend.map((t) => ({
    year: t.election_date ? t.election_date.slice(0, 4) : t.hoecha,
    득표율: t.winner_rate != null ? Number(t.winner_rate.toFixed?.(1) ?? t.winner_rate) : null,
    투표율: t.turnout != null ? Number(t.turnout.toFixed?.(1) ?? t.turnout) : null,
    color: t.color_hex,
  }));

  const winner = results.find((r) => r.is_elected) || results[0];

  return (
    <aside className="detail">
      <h2>{hist.region.name} <span className="office-badge">{office}</span></h2>

      {winner && (
        <div className="winner-card" style={{ borderLeftColor: winner.color_hex }}>
          <div className="wc-label">현재 회차 당선자</div>
          <div className="wc-name">{winner.cand}</div>
          <div className="wc-party" style={{ color: winner.color_hex }}>
            {winner.party_name} · {winner.vote_rate?.toFixed?.(1)}%
          </div>
        </div>
      )}

      {results.length > 0 && (
        <table className="results-table">
          <thead>
            <tr><th>후보</th><th>정당</th><th>득표수</th><th>득표율</th></tr>
          </thead>
          <tbody>
            {results.map((r) => (
              <tr key={r.candidate_id} className={r.is_elected ? "elected" : ""}>
                <td>{r.cand}</td>
                <td><i className="swatch sm" style={{ background: r.color_hex }} />{r.party_name}</td>
                <td>{r.votes?.toLocaleString()}</td>
                <td>{r.vote_rate?.toFixed?.(1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h3>역대 당선자</h3>
      <ul className="winners-list">
        {hist.winners.map((w) => (
          <li key={w.election_id}>
            <span className="yr">{w.election_date?.slice(0, 4)}</span>
            <i className="swatch sm" style={{ background: w.color_hex }} />
            <span>{w.cand}</span>
            <span className="party">{w.party_name}</span>
          </li>
        ))}
        {hist.winners.length === 0 && <li className="muted">데이터 없음</li>}
      </ul>

      <h3>득표·투표율 추이</h3>
      {trend.length > 0 ? (
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={trend} margin={{ top: 8, right: 12, bottom: 0, left: -10 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="year" />
            <YAxis domain={[0, 100]} unit="%" />
            <Tooltip />
            <RLegend />
            <Line type="monotone" dataKey="득표율" stroke="#152484" dot />
            <Line type="monotone" dataKey="투표율" stroke="#888" strokeDasharray="4 3" dot />
          </LineChart>
        </ResponsiveContainer>
      ) : (
        <p className="muted">추이 데이터 없음</p>
      )}
    </aside>
  );
}
