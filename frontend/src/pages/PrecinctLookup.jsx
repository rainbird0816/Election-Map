import { useEffect, useState } from "react";
import { getPresidentElections, getPresidentMap, getPrecinctLookup } from "../api";

const fmt = (n) => (n == null ? "—" : Number(n).toLocaleString());
const SIDO_ORDER = ["11", "26", "27", "28", "29", "30", "31", "36", "41", "42", "43", "44", "45", "46", "47", "48", "50"];

// 대선 투표소(투표구)·읍면동별 종합 조회 페이지
export default function PrecinctLookup() {
  const [pres, setPres] = useState([]);
  const [daesu, setDaesu] = useState(null);
  const [sidos, setSidos] = useState([]);
  const [sido, setSido] = useState(null);
  const [sggs, setSggs] = useState([]);
  const [sgg, setSgg] = useState(null);
  const [mode, setMode] = useState("투표구");
  const [data, setData] = useState(null);

  useEffect(() => { getPresidentElections().then((p) => { setPres(p); if (p.length) setDaesu(p[p.length - 1].daesu); }); }, []);

  useEffect(() => {
    if (!daesu) return;
    getPresidentMap(daesu).then((m) => {
      const ord = SIDO_ORDER.map((c) => m.find((x) => x.region_code === c)).filter(Boolean);
      setSidos(ord); setSido(ord[0]?.region_code); setSgg(null); setData(null);
    });
  }, [daesu]);

  useEffect(() => {
    if (!daesu || !sido) return;
    getPresidentMap(daesu, sido).then((m) => {
      const s = [...m].sort((a, b) => a.region_code.localeCompare(b.region_code));
      setSggs(s); setSgg(s[0]?.region_code); setData(null);
    });
  }, [daesu, sido]);

  useEffect(() => {
    if (!daesu || !sgg) return;
    getPrecinctLookup(daesu, sgg, mode).then(setData).catch(() => setData(null));
  }, [daesu, sgg, mode]);

  const cands = data?.candidates || [];
  const rows = data?.rows || [];
  const sggName = sggs.find((x) => x.region_code === sgg)?.region_name || "";

  return (
    <div className="lookup-page">
      <h2>투표소·읍면동별 종합 조회 <span className="muted">(대통령선거 개표결과)</span></h2>
      <div className="lookup-controls">
        <label>대수
          <select value={daesu ?? ""} onChange={(e) => setDaesu(Number(e.target.value))}>
            {pres.map((p) => <option key={p.daesu} value={p.daesu}>{p.name} ({p.year})</option>)}
          </select>
        </label>
        <label>시도
          <select value={sido ?? ""} onChange={(e) => setSido(e.target.value)}>
            {sidos.map((s) => <option key={s.region_code} value={s.region_code}>{s.region_name}</option>)}
          </select>
        </label>
        <label>시군구
          <select value={sgg ?? ""} onChange={(e) => setSgg(e.target.value)}>
            {sggs.map((s) => <option key={s.region_code} value={s.region_code}>{s.region_name}</option>)}
          </select>
        </label>
        <div className="seg">
          {["투표구", "읍면동"].map((m) => (
            <button key={m} className={`seg-btn ${mode === m ? "active" : ""}`} onClick={() => setMode(m)}>{m}별</button>
          ))}
        </div>
      </div>

      {!data ? <p className="muted">불러오는 중…</p> : (
        <div className="prec-wrap tall">
          <table className="prec-table">
            <thead>
              <tr>
                <th>읍면동</th><th>{mode === "읍면동" ? "구분" : "투표구"}</th><th className="num">투표수</th>
                {cands.map((c) => <th key={c.idx} className="num" title={c.party}>
                  <span className="dot" style={{ background: c.color_hex }} /> {c.name}</th>)}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i}>
                  <td>{r.dong}</td><td>{r.unit}</td><td className="num">{fmt(r.tusu)}</td>
                  {cands.map((c) => <td key={c.idx} className="num">{fmt(r.votes[c.idx])}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="muted">{sggName} · {mode}별 · 후보 전원(낙선 포함). 출처: 중앙선관위 개표결과.</p>
    </div>
  );
}
