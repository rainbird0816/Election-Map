import { useEffect, useState } from "react";
import {
  getRegionResults, getMetroSggDetail, getMetroSggPr, getCouncilDetail, getCouncilPr,
} from "../api";
import CouncilSeatsPanel from "../components/CouncilSeatsPanel.jsx";

const fmt = (n) => (n == null ? "무투표" : Number(n).toLocaleString());

// 후보 득표표: region results(cand/party_name/vote_rate) · metro detail(name/party/rate) · council(name/party/rate) 모두 수용
function CandTable({ rows }) {
  if (!rows?.length) return <p className="muted">데이터 없음</p>;
  return (
    <table className="cand-table">
      <tbody>
        {rows.map((c, i) => (
          <tr key={i} className={c.is_elected || c.elected ? "elected-row" : ""}>
            <td><span className="dot" style={{ background: c.color_hex || "#bbb" }} /></td>
            <td>{c.cand || c.name}{(c.is_elected || c.elected) ? <span className="win-tag">당선</span> : null}</td>
            <td>{c.party_name || c.party}</td>
            <td className="num">{fmt(c.votes)}</td>
            <td className="num">{(c.vote_rate ?? c.rate) != null ? `${c.vote_rate ?? c.rate}%` : ""}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// 광역비례 정당별 득표(시군구) — 의석이 아닌 득표·득표율
function PrVotes({ rows }) {
  if (!rows?.length) return <p className="muted">데이터 없음</p>;
  return (
    <table className="cand-table">
      <tbody>
        {rows.map((p, i) => (
          <tr key={i}>
            <td><span className="dot" style={{ background: p.color_hex || "#bbb" }} /></td>
            <td>{p.party}</td>
            <td className="num">{fmt(p.votes)}</td>
            <td className="num">{p.rate != null ? `${p.rate}%` : ""}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// 광역 종합 우측 패널. sggCode 있으면 시군구 모드, 없으면 시도 모드.
export default function MetroDashboard({ hoecha, sidoCode, sidoName, sggCode, sggName }) {
  const isSgg = !!sggCode;
  const [govSido, setGovSido] = useState(null);   // 시도 도지사 종합
  const [prMetro, setPrMetro] = useState(null);   // 시도 광역비례 당선자
  const [govSgg, setGovSgg] = useState(null);      // 시군구 도지사 득표
  const [council, setCouncil] = useState(null);    // 시군구 광역의원
  const [prSgg, setPrSgg] = useState(null);        // 시군구 광역비례 득표

  useEffect(() => {
    setGovSido(null); setPrMetro(null); setGovSgg(null); setCouncil(null); setPrSgg(null);
    if (!hoecha) return;
    if (isSgg) {
      getMetroSggDetail(hoecha, sggCode).then(setGovSgg).catch(() => setGovSgg([]));
      getCouncilDetail(hoecha, sggCode).then(setCouncil).catch(() => setCouncil([]));
      getMetroSggPr(hoecha, sggCode).then(setPrSgg).catch(() => setPrSgg([]));
    } else if (sidoCode) {
      getRegionResults(sidoCode, hoecha).then(setGovSido).catch(() => setGovSido([]));
      getCouncilPr(hoecha, 8, sidoCode).then(setPrMetro).catch(() => setPrMetro(null));
    }
  }, [hoecha, sidoCode, sggCode, isSgg]);

  // 시군구 모드: 광역의원(sgtype 5)만 선거구별 그룹
  const metroDistricts = {};
  for (const r of council || []) {
    if (r.sgtype !== 5) continue;
    (metroDistricts[r.sgg] || (metroDistricts[r.sgg] = [])).push(r);
  }

  if (isSgg) {
    const govWin = govSgg?.[0];
    return (
      <aside className="detail">
        <h2>{sidoName} {sggName} <span className="office-badge">광역 종합</span></h2>

        <h3 className="sec-title">광역단체장 <span className="muted">({sggName} 득표, {sidoName} 시·도지사)</span></h3>
        {govWin && (
          <div className="winner-card" style={{ borderLeftColor: govWin.color_hex }}>
            <div className="wc-label">{sggName} 최다 득표</div>
            <div className="wc-name">{govWin.name}</div>
            <div className="wc-party" style={{ color: govWin.color_hex }}>{govWin.party} {govWin.rate}%</div>
          </div>
        )}
        <CandTable rows={govSgg} />

        <h3 className="sec-title">광역의회의원 <span className="muted">(시·도의원 지역구, 낙선 포함)</span></h3>
        {Object.keys(metroDistricts).length ? Object.entries(metroDistricts).map(([sgg, cands]) => (
          <div key={sgg} className="sgg-block">
            <div className="sgg-name">{sgg}</div>
            <CandTable rows={cands} />
          </div>
        )) : <p className="muted">데이터 없음</p>}

        <h3 className="sec-title">광역비례의원 <span className="muted">({sggName} 정당 득표)</span></h3>
        <PrVotes rows={prSgg} />

        <p className="muted">중앙선관위 개표결과 · 후보·정당 전원(낙선 포함).</p>
      </aside>
    );
  }

  // 시도 모드
  const govWin = govSido?.find((c) => c.is_elected) || govSido?.[0];
  return (
    <aside className="detail">
      <h2>{sidoName} <span className="office-badge">광역 종합</span></h2>

      <h3 className="sec-title">광역단체장 <span className="muted">(시·도지사 당선, 낙선 포함)</span></h3>
      {govWin && (
        <div className="winner-card" style={{ borderLeftColor: govWin.color_hex }}>
          <div className="wc-label">당선</div>
          <div className="wc-name">{govWin.cand}</div>
          <div className="wc-party" style={{ color: govWin.color_hex }}>{govWin.party_name} {govWin.vote_rate}%</div>
        </div>
      )}
      <CandTable rows={govSido} />

      <h3 className="sec-title">광역의회 구성 <span className="muted">(광역의원+비례)</span></h3>
      <CouncilSeatsPanel hoecha={hoecha} level="metro" sido={sidoCode} heading={false} />

      <h3 className="sec-title">광역비례의원 <span className="muted">(시·도 비례 당선자)</span></h3>
      {prMetro?.parties?.length ? (
        <table className="cand-table">
          <tbody>
            {prMetro.parties.map((p, i) => (
              <tr key={i}>
                <td><span className="dot" style={{ background: p.color || "#bbb" }} /></td>
                <td>{p.party}</td>
                <td className="num">{p.seats}석</td>
                <td>{(p.names || []).join(", ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : <p className="muted">데이터 없음</p>}

      <p className="muted">시군구를 클릭하면 그 기초의 도지사·광역의원·광역비례 득표가 보입니다.</p>
    </aside>
  );
}
