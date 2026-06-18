import { useEffect, useState } from "react";
import { getPoliticianSearch, getPolitician } from "../api";

const fmt = (n) => (n == null ? "—" : Number(n).toLocaleString());
const ETYPE_BADGE = { 대선: "대통령", 총선: "국회의원", 지선: "지방선거", 보궐: "재·보궐" };

export default function PoliticianPage() {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState([]);
  const [sel, setSel] = useState(null);   // 선택된 이름
  const [data, setData] = useState(null);

  // 검색(디바운스)
  useEffect(() => {
    const t = setTimeout(() => {
      if (q.trim().length < 1) { setHits([]); return; }
      getPoliticianSearch(q.trim()).then(setHits).catch(() => setHits([]));
    }, 250);
    return () => clearTimeout(t);
  }, [q]);

  useEffect(() => {
    if (!sel) { setData(null); return; }
    setData(null);
    getPolitician(sel).then(setData).catch(() => setData(null));
  }, [sel]);

  return (
    <div className="lookup-page politician">
      <h2>정치인 검색 <span className="muted">(이름으로 역대 선거 기록)</span></h2>
      <div className="poli-search">
        <input autoFocus value={q} onChange={(e) => setQ(e.target.value)}
          placeholder="정치인 이름 입력 (예: 이재명, 오세훈)" />
        {hits.length > 0 && (
          <ul className="poli-hits">
            {hits.map((h) => (
              <li key={h.name}>
                <button className={`poli-hit ${sel === h.name ? "active" : ""}`} onClick={() => { setSel(h.name); setHits([]); setQ(h.name); }}>
                  {h.name} <span className="muted">{h.count}건</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {sel && !data && <p className="muted">불러오는 중…</p>}
      {data && (
        <div className="poli-result">
          <h3 className="sec-title">{data.name} <span className="muted">출마 {data.total}회 · 당선 {data.wins}회</span></h3>
          {data.multi && (
            <p className="hint">※ 지역(시도)별로 묶었습니다. 같은 이름이 여러 지역에 있으면 <b>동명이인</b>일 수 있습니다
              (전국 단위 인물은 여러 지역에 걸쳐 표시됨).</p>
          )}
          {data.groups.map((g) => (
            <div key={g.sido} className="poli-group">
              <div className="poli-group-head">{g.sido} <span className="muted">기록 {g.records.length} · 당선 {g.wins}</span></div>
              <table className="cand-table">
                <tbody>
                  {g.records.map((r, i) => (
                    <tr key={i} className={r.elected ? "elected-row" : ""}>
                      <td className="poli-yr2">{r.year}</td>
                      <td><span className="badge-sm">{ETYPE_BADGE[r.etype] || r.etype}</span></td>
                      <td>{r.office}{r.sub ? <span className="muted"> {r.sub}</span> : null}</td>
                      <td className="poli-region">{r.region}</td>
                      <td><span className="dot" style={{ background: r.color }} />{r.party}</td>
                      <td className="num">{r.rate != null ? `${r.rate}%` : (r.votes != null ? fmt(r.votes) : "")}</td>
                      <td>{r.elected ? <span className="win-tag">당선</span> : null}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
          {data.records.length === 0 && <p className="muted">기록 없음</p>}
        </div>
      )}
      {!sel && <p className="muted">이름을 입력하면 후보 목록이 뜨고, 선택하면 대선·총선·단체장·지방의원·재보궐 출마 이력이 연도별로 표시됩니다.</p>}
    </div>
  );
}
