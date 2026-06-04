import { useEffect, useState } from "react";
import {
  getPresidentElections, getPresidentMap, getPrecinctLookup,
  getAssemblyDaesu, getAssemblyKeys, getAssemblyDistrict,
} from "../api";

const fmt = (n) => (n == null ? "—" : Number(n).toLocaleString());
const SIDO = [
  ["11", "서울특별시"], ["26", "부산광역시"], ["27", "대구광역시"], ["28", "인천광역시"],
  ["29", "광주광역시"], ["30", "대전광역시"], ["31", "울산광역시"], ["36", "세종특별자치시"],
  ["41", "경기도"], ["42", "강원특별자치도"], ["43", "충청북도"], ["44", "충청남도"],
  ["45", "전북특별자치도"], ["46", "전라남도"], ["47", "경상북도"], ["48", "경상남도"], ["50", "제주특별자치도"],
];

// 투표구별 votes_json(후보 idx순) → 읍면동 집계
function aggDong(rows, ncand) {
  const agg = {};
  for (const p of rows) {
    const a = agg[p.dong || "기타"] || (agg[p.dong || "기타"] = { tusu: 0, votes: Array(ncand).fill(0) });
    a.tusu += p.tusu || 0;
    p.votes.forEach((v, i) => { a.votes[i] += v || 0; });
  }
  return Object.entries(agg).map(([dong, a]) => ({ dong, unit: "(읍면동 계)", tusu: a.tusu, votes: a.votes }));
}

export default function PrecinctLookup() {
  const [mode, setMode] = useState("대선");        // 대선 | 총선
  const [grain, setGrain] = useState("투표구");     // 투표구 | 읍면동
  const [elecs, setElecs] = useState([]);
  const [daesu, setDaesu] = useState(null);
  const [sido, setSido] = useState("11");
  const [units, setUnits] = useState([]);          // 시군구(대선) 또는 선거구(총선) 목록
  const [unit, setUnit] = useState(null);          // 선택된 시군구 code(대선) / 선거구 key(총선)
  const [data, setData] = useState(null);          // {candidates, rows}

  // 선거 목록(모드별)
  useEffect(() => {
    const fn = mode === "대선" ? getPresidentElections() : getAssemblyDaesu();
    fn.then((e) => { setElecs(e); setDaesu(e[0]?.daesu ?? null); }).catch(() => setElecs([]));
  }, [mode]);

  // 시도 변경 → 하위 단위(시군구/선거구) 목록
  useEffect(() => {
    setUnits([]); setUnit(null); setData(null);
    if (!daesu) return;
    if (mode === "대선") {
      getPresidentMap(daesu, sido).then((m) => {
        const s = [...m].sort((a, b) => a.region_code.localeCompare(b.region_code))
          .map((x) => ({ id: x.region_code, label: x.region_name }));
        setUnits(s); setUnit(s[0]?.id ?? null);
      }).catch(() => setUnits([]));
    } else {
      getAssemblyKeys(daesu, sido).then((ks) => {
        const s = ks.map((k) => ({ id: k.key, label: k.sgg }));
        setUnits(s); setUnit(s[0]?.id ?? null);
      }).catch(() => setUnits([]));
    }
  }, [mode, daesu, sido]);

  // 단위 선택 → 데이터
  useEffect(() => {
    setData(null);
    if (!daesu || !unit) return;
    if (mode === "대선") {
      getPrecinctLookup(daesu, unit, grain)
        .then((d) => setData({ candidates: d.candidates, rows: d.rows })).catch(() => setData(null));
    } else {
      getAssemblyDistrict(daesu, unit).then((d) => {
        let rows = d.precincts.map((p) => ({ dong: p.dong, unit: p.unit, tusu: p.tusu,
          votes: (() => { try { return JSON.parse(p.votes_json); } catch { return []; } })() }));
        if (grain === "읍면동") rows = aggDong(rows, d.candidates.length);
        setData({ candidates: d.candidates, rows });
      }).catch(() => setData(null));
    }
  }, [mode, daesu, unit, grain]);

  const cands = data?.candidates || [];
  const rows = data?.rows || [];
  const unitLabel = mode === "대선" ? "시군구" : "선거구";

  return (
    <div className="lookup-page">
      <h2>투표소·읍면동별 종합 조회</h2>
      <div className="lookup-controls">
        <div className="seg">
          {["대선", "총선"].map((m) => (
            <button key={m} className={`seg-btn ${mode === m ? "active" : ""}`} onClick={() => setMode(m)}>
              {m === "대선" ? "대통령" : "국회의원"}
            </button>
          ))}
        </div>
        <label>{mode === "대선" ? "대수" : "대수"}
          <select value={daesu ?? ""} onChange={(e) => setDaesu(Number(e.target.value))}>
            {elecs.map((e) => <option key={e.daesu} value={e.daesu}>{e.name}{e.year ? ` (${e.year})` : ""}</option>)}
          </select>
        </label>
        <label>시도
          <select value={sido} onChange={(e) => setSido(e.target.value)}>
            {SIDO.map(([c, n]) => <option key={c} value={c}>{n}</option>)}
          </select>
        </label>
        <label>{unitLabel}
          <select value={unit ?? ""} onChange={(e) => setUnit(e.target.value)}>
            {units.map((u) => <option key={u.id} value={u.id}>{u.label}</option>)}
          </select>
        </label>
        <div className="seg">
          {["투표구", "읍면동"].map((g) => (
            <button key={g} className={`seg-btn ${grain === g ? "active" : ""}`} onClick={() => setGrain(g)}>{g}별</button>
          ))}
        </div>
      </div>

      {mode === "총선" && !units.length && daesu && (
        <p className="hint">이 대수·시도의 투표구 데이터가 없습니다(투표구별은 21·22대만 제공).</p>
      )}
      {!data ? <p className="muted">불러오는 중…</p> : (
        <div className="prec-wrap tall">
          <table className="prec-table">
            <thead>
              <tr>
                <th>읍면동</th><th>{grain === "읍면동" ? "구분" : "투표구"}</th><th className="num">투표수</th>
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
      <p className="muted">후보 전원(낙선 포함). 출처: 중앙선관위 개표결과. 지선은 선관위가 투표구별을 제공하지 않아 제외(지방선거 탭에서 시군구 단위 확인).</p>
    </div>
  );
}
