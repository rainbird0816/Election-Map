import { useEffect, useMemo, useState } from "react";
import { getWinners } from "../api";

// 배경색 대비 글자색(밝으면 검정, 어두우면 흰색)
function textOn(hex) {
  if (!hex || hex[0] !== "#" || hex.length < 7) return "#111";
  const r = parseInt(hex.slice(1, 3), 16), g = parseInt(hex.slice(3, 5), 16), b = parseInt(hex.slice(5, 7), 16);
  return (0.299 * r + 0.587 * g + 0.114 * b) > 150 ? "#111" : "#fff";
}

function Cell({ cell }) {
  if (!cell || !cell.name) return <td className="win-cell empty">—</td>;
  const bg = cell.color_hex || "#bbb";
  return (
    <td className="win-cell" style={{ background: bg, color: textOn(bg) }} title={cell.party}>
      <span className="wc-name">{cell.name}</span>
      <span className="wc-party">{cell.party}</span>
    </td>
  );
}

export default function WinnersPage() {
  const [metro, setMetro] = useState(null);     // 전국(광역단체장)
  const [basic, setBasic] = useState(null);     // 선택 시도의 기초단체장
  const [sido, setSido] = useState(null);       // {code, name}
  const [sgg, setSgg] = useState(null);         // {code, name}

  useEffect(() => { getWinners("metro").then(setMetro).catch(() => setMetro({ columns: [], regions: [] })); }, []);

  useEffect(() => {
    setBasic(null); setSgg(null);
    if (!sido) return;
    getWinners("basic", sido.code).then(setBasic).catch(() => setBasic({ columns: [], regions: [] }));
  }, [sido]);

  const cols = (sido ? basic : metro)?.columns || [];
  const sidoRow = useMemo(
    () => (sido && metro ? metro.regions.find((r) => r.region_code === sido.code) : null),
    [sido, metro]);
  const sggRow = useMemo(
    () => (sgg && basic ? basic.regions.find((r) => r.region_code === sgg.code) : null),
    [sgg, basic]);

  function Matrix({ data, colLabel, onRow, activeCode }) {
    if (!data) return <p className="muted">불러오는 중…</p>;
    return (
      <div className="win-wrap">
        <table className="win-table">
          <thead>
            <tr>
              <th className="win-rowhead">{colLabel}</th>
              {data.columns.map((c) => (
                <th key={c.election_id} className="num">{c.year}<span className="muted"> {c.hoecha}회</span></th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.regions.map((r) => (
              <tr key={r.region_code} className={r.region_code === activeCode ? "active" : ""}>
                <th className="win-rowhead clickable" onClick={() => onRow(r)}>{r.region_name} ›</th>
                {data.columns.map((c) => <Cell key={c.election_id} cell={r.cells[c.election_id]} />)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <div className="lookup-page winners-page">
      <h2>역대 단체장 당선인</h2>
      <div className="crumbs win-crumbs">
        <button className="crumb" onClick={() => { setSido(null); setSgg(null); }} disabled={!sido}>전국 · 광역단체장</button>
        {sido && (
          <>
            <span className="sep">›</span>
            <button className="crumb" onClick={() => setSgg(null)} disabled={!sgg}>{sido.name} · 기초단체장</button>
          </>
        )}
        {sgg && (<><span className="sep">›</span><span className="crumb cur">{sgg.name}</span></>)}
      </div>

      {!sido ? (
        <>
          <p className="muted">시도별 광역단체장(시·도지사) 당선인입니다. 셀 색은 당선인 정당색. 행을 클릭하면 그 시도의 기초단체장으로 들어갑니다.</p>
          <Matrix data={metro} colLabel="시도 / 연도" onRow={(r) => setSido({ code: r.region_code, name: r.region_name })} />
        </>
      ) : (
        <>
          {/* 선택 시도의 광역단체장 띠 */}
          {sidoRow && (
            <div className="win-strip">
              <span className="strip-label">{sido.name} 시·도지사</span>
              {cols.map((c) => {
                const cell = sidoRow.cells[c.election_id];
                const bg = cell?.color_hex || "#eee";
                return (
                  <span key={c.election_id} className="strip-chip" style={{ background: bg, color: textOn(bg) }}>
                    <b>{c.year}</b> {cell?.name || "—"}<small>{cell?.party || ""}</small>
                  </span>
                );
              })}
            </div>
          )}

          {sggRow && (
            <div className="win-strip detail">
              <span className="strip-label">{sgg.name} 청장</span>
              {cols.map((c) => {
                const cell = sggRow.cells[c.election_id];
                const bg = cell?.color_hex || "#eee";
                return (
                  <span key={c.election_id} className="strip-chip" style={{ background: bg, color: textOn(bg) }}>
                    <b>{c.year}</b> {cell?.name || "—"}<small>{cell?.party || ""}</small>
                  </span>
                );
              })}
            </div>
          )}

          <p className="muted">{sido.name} 기초단체장(구·시·군의 장) 당선인. 행을 클릭하면 해당 기초자치단체 이력만 봅니다.</p>
          <Matrix data={basic} colLabel="시군구 / 연도"
            onRow={(r) => setSgg({ code: r.region_code, name: r.region_name })} activeCode={sgg?.code} />
        </>
      )}
      <p className="muted">당선인만 표시(낙선 제외). 출처: 중앙선거관리위원회. 광역·기초단체장 3~8회(2002~2022).</p>
    </div>
  );
}
