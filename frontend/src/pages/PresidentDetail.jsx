import { useEffect, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, Legend as RLegend, ResponsiveContainer, CartesianGrid,
} from "recharts";
import { getPresidentRegion, getPresidentHistory } from "../api";

const fmt = (n) => (n == null ? "—" : Number(n).toLocaleString());
const CAMPS = ["민주", "보수", "진보", "중도"];

export default function PresidentDetail({ daesu, code, name }) {
  const [data, setData] = useState(null);
  const [hist, setHist] = useState(null);
  const [err, setErr] = useState(null);
  const [openPrec, setOpenPrec] = useState(false);

  useEffect(() => {
    setData(null); setErr(null); setOpenPrec(false); setHist(null);
    if (!daesu || !code) return;
    getPresidentRegion(daesu, code).then(setData).catch((e) => setErr(String(e)));
    getPresidentHistory(code).then(setHist).catch(() => setHist(null));
  }, [daesu, code]);

  if (!code) return <div className="detail empty">지역을 클릭하세요.</div>;
  if (err) return <p className="hint">상세를 불러오지 못했습니다. ({err})</p>;
  if (!data) return <p className="muted">불러오는 중…</p>;

  const cands = data.candidates || [];
  const precs = data.precincts || [];
  const cols = cands;

  return (
    <>
      <h2>{name} <span className="office-badge">대통령선거</span></h2>
      <h3 className="sec-title">후보별 득표 <span className="muted">(낙선 포함 {cands.length}명)</span></h3>
      <table className="cand-table">
        <thead><tr><th></th><th>후보</th><th>정당</th><th className="num">득표수</th><th className="num">득표율</th></tr></thead>
        <tbody>
          {cands.map((c, i) => (
            <tr key={c.idx} className={i === 0 ? "elected-row" : ""}>
              <td><span className="dot" style={{ background: c.color_hex || "#bbb" }} /></td>
              <td>{c.name}{i === 0 ? <span className="win-tag">1위</span> : null}</td>
              <td>{c.party}</td>
              <td className="num">{fmt(c.votes)}</td>
              <td className="num">{c.rate}%</td>
            </tr>
          ))}
        </tbody>
      </table>

      {precs.length > 0 && (
        <>
          <button className="link-btn" onClick={() => setOpenPrec((v) => !v)}>
            {openPrec ? "▾" : "▸"} 투표구별 결과 ({precs.length}개)
          </button>
          {openPrec && (
            <div className="prec-wrap">
              <table className="prec-table">
                <thead>
                  <tr><th>읍면동</th><th>투표구</th><th className="num">투표수</th>
                    {cols.map((c) => <th key={c.idx} className="num" title={c.party}>{c.name}</th>)}</tr>
                </thead>
                <tbody>
                  {precs.map((p, i) => {
                    let v = []; try { v = JSON.parse(p.votes_json); } catch { v = []; }
                    return (
                      <tr key={i}>
                        <td>{p.dong}</td><td>{p.unit}</td><td className="num">{fmt(p.tusu)}</td>
                        {cols.map((c) => <td key={c.idx} className="num">{fmt(v[c.idx])}</td>)}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {hist?.trend?.length > 0 && (
        <>
          <h3 className="sec-title">역대 대선 진영별 득표율 추이</h3>
          <ResponsiveContainer width="100%" height={210}>
            <LineChart data={hist.trend} margin={{ top: 5, right: 8, bottom: 0, left: -18 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
              <XAxis dataKey="year" fontSize={11} />
              <YAxis fontSize={11} unit="%" />
              <Tooltip formatter={(v) => `${v}%`} />
              <RLegend wrapperStyle={{ fontSize: 12 }} />
              {CAMPS.map((c) => (
                <Line key={c} type="monotone" dataKey={c} name={c}
                  stroke={hist.camp_color[c]} strokeWidth={2} dot={{ r: 2 }} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </>
      )}

      {hist?.winners?.length > 0 && (
        <>
          <h3 className="sec-title">역대 대선 1위</h3>
          <ul className="winners-list">
            {hist.winners.map((h) => (
              <li key={h.daesu}>
                <span className="yr">{h.year}</span>
                <span className="swatch sm" style={{ background: h.color_hex }} />
                {h.winner_name}
                <span className="party">{h.winner_party} {h.winner_rate}%</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </>
  );
}
