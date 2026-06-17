import { useEffect, useState } from "react";
import { getRegionResults, getRegionHistory, getCouncilDetail, getCouncilPr } from "../api";
import CouncilSeatsPanel from "../components/CouncilSeatsPanel.jsx";

const fmt = (n) => (n == null ? "무투표" : Number(n).toLocaleString());

// 비례대표(광역비례 8 / 기초비례 9): 정당별 의석 + 당선자 명단
function PrSection({ pr }) {
  if (!pr?.parties?.length) return <p className="muted">데이터 없음</p>;
  return (
    <table className="cand-table">
      <tbody>
        {pr.parties.map((p, i) => (
          <tr key={i}>
            <td><span className="dot" style={{ background: p.color || "#bbb" }} /></td>
            <td>{p.party}</td>
            <td className="num">{p.seats}석</td>
            <td>{(p.names || []).join(", ")}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function CandTable({ rows, winnerTag = "당선" }) {
  if (!rows?.length) return <p className="muted">데이터 없음</p>;
  return (
    <table className="cand-table">
      <tbody>
        {rows.map((c, i) => (
          <tr key={i} className={c.is_elected || c.elected ? "elected-row" : ""}>
            <td><span className="dot" style={{ background: c.color_hex || "#bbb" }} /></td>
            <td>{c.cand || c.name}{(c.is_elected || c.elected) ? <span className="win-tag">{winnerTag}</span> : null}</td>
            <td>{c.party_name || c.party}</td>
            <td className="num">{fmt(c.votes)}</td>
            <td className="num">{(c.vote_rate ?? c.rate) != null ? `${c.vote_rate ?? c.rate}%` : ""}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// 시군구 종합: 광역단체장(시도) → 기초단체장 → 광역의원 → 기초의원 한 화면
export default function SigunguDashboard({ hoecha, sggCode, sggName, sidoCode, sidoName }) {
  const [metro, setMetro] = useState(null);
  const [basic, setBasic] = useState(null);
  const [hist, setHist] = useState(null);
  const [council, setCouncil] = useState(null);
  const [prMetro, setPrMetro] = useState(null); // 광역비례(시도 단위)
  const [prBasic, setPrBasic] = useState(null); // 기초비례(시군구 단위)

  useEffect(() => {
    setMetro(null); setBasic(null); setHist(null); setCouncil(null);
    setPrMetro(null); setPrBasic(null);
    if (!hoecha || !sggCode) return;
    getRegionResults(sidoCode, hoecha).then(setMetro).catch(() => setMetro([]));
    getRegionResults(sggCode, hoecha).then(setBasic).catch(() => setBasic([]));
    getRegionHistory(sggCode, "기초단체장").then(setHist).catch(() => setHist(null));
    getCouncilDetail(hoecha, sggCode).then(setCouncil).catch(() => setCouncil([]));
    if (sidoCode) getCouncilPr(hoecha, 8, sidoCode).then(setPrMetro).catch(() => setPrMetro(null));
    getCouncilPr(hoecha, 9, null, sggCode).then(setPrBasic).catch(() => setPrBasic(null));
  }, [hoecha, sggCode, sidoCode]);

  const metroWin = metro?.[0];
  // 지방의원 선거구별 그룹
  const groups = { 5: {}, 6: {} };
  for (const r of council || []) {
    const g = groups[r.sgtype]; if (!g) continue;
    (g[r.sgg] || (g[r.sgg] = [])).push(r);
  }

  return (
    <aside className="detail">
      <h2>{sidoName} {sggName} <span className="office-badge">종합</span></h2>

      <h3 className="sec-title">기초의회 의석분포 <span className="muted">(기초의원+기초비례)</span></h3>
      <CouncilSeatsPanel hoecha={hoecha} level="basic" sigungu={sggCode} heading={false} />

      <h3 className="sec-title">광역단체장 <span className="muted">({sidoName} 시·도지사)</span></h3>
      {metroWin ? (
        <div className="winner-card" style={{ borderLeftColor: metroWin.color_hex }}>
          <div className="wc-label">당선</div>
          <div className="wc-name">{metroWin.cand}</div>
          <div className="wc-party" style={{ color: metroWin.color_hex }}>
            {metroWin.party_name} {metroWin.vote_rate}%
          </div>
        </div>
      ) : <p className="muted">데이터 없음</p>}

      <h3 className="sec-title">기초단체장 <span className="muted">(구청장·시장·군수)</span></h3>
      <CandTable rows={basic} />

      <h3 className="sec-title">광역의원 (시·도의원)</h3>
      {Object.keys(groups[5]).length ? Object.entries(groups[5]).map(([sgg, cands]) => (
        <div key={sgg} className="sgg-block">
          <div className="sgg-name">{sgg}</div>
          <CandTable rows={cands} />
        </div>
      )) : <p className="muted">데이터 없음</p>}

      <h3 className="sec-title">광역비례의원 <span className="muted">({sidoName} 시·도 비례, 당선자)</span></h3>
      <PrSection pr={prMetro} />

      <h3 className="sec-title">기초의원 (구·시·군의원)</h3>
      {Object.keys(groups[6]).length ? Object.entries(groups[6]).map(([sgg, cands]) => (
        <div key={sgg} className="sgg-block">
          <div className="sgg-name">{sgg}</div>
          <CandTable rows={cands} />
        </div>
      )) : <p className="muted">데이터 없음</p>}

      <h3 className="sec-title">기초비례의원 <span className="muted">({sggName} 비례, 당선자)</span></h3>
      <PrSection pr={prBasic} />

      {hist?.winners?.length > 0 && (
        <>
          <h3 className="sec-title">역대 기초단체장</h3>
          <ul className="winners-list">
            {hist.winners.map((w) => (
              <li key={w.election_id}>
                <span className="yr">{w.hoecha}회</span>
                <span className="swatch sm" style={{ background: w.color_hex }} />
                {w.cand}<span className="party">{w.party_name}</span>
              </li>
            ))}
          </ul>
        </>
      )}
      <p className="muted">중앙선관위 개표결과.</p>
    </aside>
  );
}
