import { useEffect, useState } from "react";
import { getAssemblyDistrict } from "../api";

const fmt = (n) => (n == null ? "—" : Number(n).toLocaleString());

export default function AssemblyDistrictDetail({ daesu, dkey }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [openPrec, setOpenPrec] = useState(false);

  useEffect(() => {
    setData(null); setErr(null); setOpenPrec(false);
    if (!daesu || !dkey) return;
    getAssemblyDistrict(daesu, dkey).then(setData).catch((e) => setErr(String(e)));
  }, [daesu, dkey]);

  if (!dkey) return null;
  if (err) return <p className="hint">상세 데이터를 불러오지 못했습니다. ({err})</p>;
  if (!data) return <p className="muted">불러오는 중…</p>;

  const cands = data.candidates || [];
  const precs = data.precincts || [];
  // 투표구 표 컬럼 = 득표순 후보. votes_json 은 idx 순서 → idx로 매핑.
  const cols = cands; // 이미 득표순
  const colIdx = cols.map((c) => c.idx);

  return (
    <>
      <h3 className="sec-title">후보별 득표 <span className="muted">({cands.length}명)</span></h3>
      <table className="cand-table">
        <thead>
          <tr><th></th><th>후보</th><th>정당</th><th className="num">득표수</th><th className="num">득표율</th></tr>
        </thead>
        <tbody>
          {cands.map((c) => (
            <tr key={c.idx} className={c.elected ? "elected-row" : ""}>
              <td><span className="dot" style={{ background: c.color_hex || "#bbb" }} /></td>
              <td>{c.name}{c.elected ? <span className="win-tag">당선</span> : null}</td>
              <td>{c.party}</td>
              <td className="num">{fmt(c.votes)}</td>
              <td className="num">{c.rate}%</td>
            </tr>
          ))}
        </tbody>
      </table>

      <button className="link-btn" onClick={() => setOpenPrec((v) => !v)}>
        {openPrec ? "▾" : "▸"} 투표구별 결과 ({precs.length}개 투표구)
      </button>
      {openPrec && (
        <div className="prec-wrap">
          <table className="prec-table">
            <thead>
              <tr>
                <th>읍면동</th><th>투표구</th><th className="num">투표수</th>
                {cols.map((c) => <th key={c.idx} className="num" title={c.party}>{c.name}</th>)}
              </tr>
            </thead>
            <tbody>
              {precs.map((p, i) => {
                let v = [];
                try { v = JSON.parse(p.votes_json); } catch { v = []; }
                return (
                  <tr key={i}>
                    <td>{p.dong}</td><td>{p.unit}</td><td className="num">{fmt(p.tusu)}</td>
                    {colIdx.map((ix) => <td key={ix} className="num">{fmt(v[ix])}</td>)}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
