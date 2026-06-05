import { useEffect, useMemo, useState } from "react";
import MapKorea from "../maps/MapKorea.jsx";
import MapSigungu from "../maps/MapSigungu.jsx";
import Legend from "../components/Legend.jsx";
import RegionTimeline from "./RegionTimeline.jsx";
import {
  getWinners, getWinnersSummary, getElections, getPresidentElections,
  getMap, getCouncilMap, getMetroSggMap, getBasicSidoMap, getPresidentMap,
} from "../api";

// 배경색 대비 글자색(밝으면 검정, 어두우면 흰색)
function textOn(hex) {
  if (!hex || hex[0] !== "#" || hex.length < 7) return "#111";
  const r = parseInt(hex.slice(1, 3), 16), g = parseInt(hex.slice(3, 5), 16), b = parseInt(hex.slice(5, 7), 16);
  return (0.299 * r + 0.587 * g + 0.114 * b) > 150 ? "#111" : "#fff";
}

// 지도 모드 선거종류 → 지도 데이터 fetch 방식(기존 엔드포인트 재사용)
const MAP_TYPES = ["대통령", "시도지사", "시군구청장", "광역의원", "기초의원"];

export default function WinnersPage() {
  const [winMode, setWinMode] = useState("map"); // map | table

  return (
    <div className="lookup-page winners-page">
      <div className="win-modehead">
        <h2>역대 당선인 · 지역별</h2>
        <div className="seg">
          {[["map", "지도·연표"], ["table", "전국 요약표"]].map(([v, l]) => (
            <button key={v} className={`seg-btn ${winMode === v ? "active" : ""}`} onClick={() => setWinMode(v)}>{l}</button>
          ))}
        </div>
      </div>
      {winMode === "map" ? <MapMode /> : <TableMode />}
    </div>
  );
}

/* ───────────────────────── 지도 + 종합 연표 ───────────────────────── */
function MapMode() {
  const [type, setType] = useState("시군구청장");
  const [jisun, setJisun] = useState([]);   // 지선 회차 목록
  const [pres, setPres] = useState([]);     // 대선 대수 목록
  const [elec, setElec] = useState(null);   // 선택값(대통령=daesu, 그 외=지선 election_id=hoecha)
  const [view, setView] = useState("sido"); // sido | sigungu
  const [sido, setSido] = useState(null);   // {code, name}
  const [sel, setSel] = useState(null);     // 선택 시군구 {code, name} → 연표
  const [sidoMap, setSidoMap] = useState([]);
  const [sggMap, setSggMap] = useState([]);

  const isPres = type === "대통령";

  useEffect(() => {
    getElections().then((e) => setJisun(e.filter((x) => x.type === "지선"))).catch(() => setJisun([]));
    getPresidentElections().then(setPres).catch(() => setPres([]));
  }, []);

  // 선거종류/목록 로드 시 기본 연도(최신)
  useEffect(() => {
    setView("sido"); setSido(null); setSel(null); setSggMap([]);
    if (isPres) { if (pres.length) setElec(pres[pres.length - 1].daesu); }
    else if (jisun.length) setElec(jisun[jisun.length - 1].id);
  }, [type, jisun.length, pres.length]);

  const opts = isPres
    ? pres.map((p) => ({ value: p.daesu, label: `${p.name} (${p.year})` }))
    : jisun.map((e) => ({ value: e.id, label: `${e.name} (${e.election_date?.slice(0, 4)})` }));

  function fetchSido() {
    if (isPres) return getPresidentMap(elec);
    if (type === "시도지사") return getMap(elec, "광역단체장");
    if (type === "시군구청장") return getBasicSidoMap(elec);
    if (type === "광역의원") return getCouncilMap(elec, 5);
    return getCouncilMap(elec, 6);
  }
  function fetchSgg(sc) {
    if (isPres) return getPresidentMap(elec, sc);
    if (type === "시도지사") return getMetroSggMap(elec, sc);
    if (type === "시군구청장") return getMap(elec, "기초단체장", sc);
    if (type === "광역의원") return getCouncilMap(elec, 5, sc);
    return getCouncilMap(elec, 6, sc);
  }

  useEffect(() => {
    if (elec == null) return;
    fetchSido().then(setSidoMap).catch(() => setSidoMap([]));
  }, [type, elec]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (view !== "sigungu" || !sido || elec == null) { return; }
    fetchSgg(sido.code).then(setSggMap).catch(() => setSggMap([]));
  }, [view, sido, type, elec]); // eslint-disable-line react-hooks/exhaustive-deps

  const sidoColor = useMemo(() => Object.fromEntries(sidoMap.map((d) => [d.region_code, d.color_hex])), [sidoMap]);
  const sggColor = useMemo(() => Object.fromEntries(sggMap.map((d) => [d.region_code, d.color_hex])), [sggMap]);
  const nameOfSido = (c) => sidoMap.find((d) => d.region_code === c)?.region_name || c;

  function onSido(code) {
    setSido({ code, name: nameOfSido(code) }); setView("sigungu"); setSel(null); setSggMap([]);
  }
  function onSgg(code) {
    setSel({ code, name: sggMap.find((d) => d.region_code === code)?.region_name || "시군구" });
  }

  return (
    <>
      <div className="lookup-controls winmap-controls">
        <div className="seg">
          {MAP_TYPES.map((t) => (
            <button key={t} className={`seg-btn ${type === t ? "active" : ""}`} onClick={() => setType(t)}>{t}</button>
          ))}
        </div>
        <label>{isPres ? "대수" : "회차"}
          <select value={elec ?? ""} onChange={(e) => { setElec(Number(e.target.value)); setSel(null); }}>
            {opts.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </label>
        <div className="crumbs win-crumbs">
          <button className="crumb" onClick={() => { setView("sido"); setSido(null); setSel(null); setSggMap([]); }}
            disabled={view === "sido"}>전국</button>
          {sido && <><span className="sep">›</span><span className="crumb cur">{sido.name}</span></>}
        </div>
      </div>

      <div className="winmap-layout">
        <section className="map-pane">
          {view === "sido" ? (
            <>
              <MapKorea colorByCode={sidoColor} selectedCode={sido?.code} onSelect={onSido} />
              <Legend mapData={sidoMap} />
            </>
          ) : (
            <>
              <MapSigungu sidoCode={sido.code} electionId={null} colorByCode={sggColor}
                selectedCode={sel?.code} onSelect={onSgg} />
              <Legend mapData={sggMap} />
              {sggMap.length === 0 && <p className="hint">이 시도의 데이터가 없습니다.</p>}
            </>
          )}
          <p className="muted">지도 색 = {isPres ? "대선" : type} {isPres ? "1위 후보" : ""} 정당색. 시도→시군구로 들어간 뒤 시군구를 클릭하면 그 지역의 모든 선출직 연표가 보입니다.</p>
        </section>

        <aside className="detail winmap-detail">
          {sel ? <RegionTimeline code={sel.code} name={sel.name} />
            : <p className="muted">{view === "sido" ? "시도를 클릭해 들어간 뒤" : "시군구를 클릭하면"} 그 지역에서 뽑는 모든 선출직(대통령·국회의원·시도지사·시군구청장·광역/기초의원·교육감)의 역대 결과가 연도별로 표시됩니다.</p>}
        </aside>
      </div>
    </>
  );
}

/* ───────────────────────── 전국 요약표(기존) ───────────────────────── */
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

function TableMode() {
  const [metro, setMetro] = useState(null);
  const [basic, setBasic] = useState(null);
  const [sido, setSido] = useState(null);
  const [sgg, setSgg] = useState(null);
  const [summary, setSummary] = useState(null);
  const [sumLevel, setSumLevel] = useState("metro");

  useEffect(() => { getWinners("metro").then(setMetro).catch(() => setMetro({ columns: [], regions: [] })); }, []);
  useEffect(() => { getWinnersSummary().then(setSummary).catch(() => setSummary(null)); }, []);
  useEffect(() => {
    setBasic(null); setSgg(null);
    if (!sido) return;
    getWinners("basic", sido.code).then(setBasic).catch(() => setBasic({ columns: [], regions: [] }));
  }, [sido]);

  const cols = (sido ? basic : metro)?.columns || [];
  const sidoRow = useMemo(() => (sido && metro ? metro.regions.find((r) => r.region_code === sido.code) : null), [sido, metro]);
  const sggRow = useMemo(() => (sgg && basic ? basic.regions.find((r) => r.region_code === sgg.code) : null), [sgg, basic]);

  function Matrix({ data, colLabel, onRow, activeCode }) {
    if (!data) return <p className="muted">불러오는 중…</p>;
    return (
      <div className="win-wrap">
        <table className="win-table">
          <thead>
            <tr>
              <th className="win-rowhead">{colLabel}</th>
              {data.columns.map((c) => <th key={c.election_id} className="num">{c.year}<span className="muted"> {c.hoecha}회</span></th>)}
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

  function Summary() {
    if (!summary) return null;
    const data = summary[sumLevel];
    const scols = summary.columns;
    const parties = data.parties.filter((p) => p.total > 0);
    const officeLabel = sumLevel === "metro" ? "광역단체장(시·도지사)" : "기초단체장(구·시·군의 장)";
    return (
      <div className="win-sum">
        <div className="win-sum-head">
          <b>전국 정당별 의석 — 연도별</b>
          <div className="seg">
            {[["metro", "광역단체장"], ["basic", "기초단체장"]].map(([v, l]) => (
              <button key={v} className={`seg-btn ${sumLevel === v ? "active" : ""}`} onClick={() => setSumLevel(v)}>{l}</button>
            ))}
          </div>
        </div>
        <div className="sum-bars">
          {scols.map((c) => {
            const total = data.totals[c.election_id] || 0;
            return (
              <div key={c.election_id} className="sum-row">
                <span className="sum-year">{c.year}<small> {c.hoecha}회</small></span>
                <div className="sum-bar">
                  {parties.map((p) => {
                    const n = p.cells[c.election_id] || 0;
                    if (!n) return null;
                    const pct = total ? (n / total) * 100 : 0;
                    return <span key={p.party} className="sum-seg" title={`${p.party} ${n}석`}
                      style={{ width: pct + "%", background: p.color, color: textOn(p.color) }}>{pct >= 7 ? n : ""}</span>;
                  })}
                </div>
                <span className="sum-total">{total}석</span>
              </div>
            );
          })}
        </div>
        <div className="sum-legend">
          {parties.map((p) => <span key={p.party} className="sum-leg"><span className="dot" style={{ background: p.color }} /> {p.party}<span className="muted"> {p.total}</span></span>)}
        </div>
        <p className="muted">{officeLabel} 당선인 수(낙선 제외). 막대는 회차별 합 100% 기준 정당 점유.</p>
      </div>
    );
  }

  return (
    <>
      <div className="crumbs win-crumbs">
        <button className="crumb" onClick={() => { setSido(null); setSgg(null); }} disabled={!sido}>전국 · 광역단체장</button>
        {sido && <><span className="sep">›</span><button className="crumb" onClick={() => setSgg(null)} disabled={!sgg}>{sido.name} · 기초단체장</button></>}
        {sgg && <><span className="sep">›</span><span className="crumb cur">{sgg.name}</span></>}
      </div>

      {!sido ? (
        <>
          <Summary />
          <p className="muted">시도별 광역단체장(시·도지사) 당선인입니다. 셀 색은 당선인 정당색. 행을 클릭하면 그 시도의 기초단체장으로 들어갑니다.</p>
          <Matrix data={metro} colLabel="시도 / 연도" onRow={(r) => setSido({ code: r.region_code, name: r.region_name })} />
        </>
      ) : (
        <>
          {sidoRow && (
            <div className="win-strip">
              <span className="strip-label">{sido.name} 시·도지사</span>
              {cols.map((c) => { const cell = sidoRow.cells[c.election_id]; const bg = cell?.color_hex || "#eee";
                return <span key={c.election_id} className="strip-chip" style={{ background: bg, color: textOn(bg) }}><b>{c.year}</b> {cell?.name || "—"}<small>{cell?.party || ""}</small></span>; })}
            </div>
          )}
          {sggRow && (
            <div className="win-strip detail">
              <span className="strip-label">{sgg.name} 청장</span>
              {cols.map((c) => { const cell = sggRow.cells[c.election_id]; const bg = cell?.color_hex || "#eee";
                return <span key={c.election_id} className="strip-chip" style={{ background: bg, color: textOn(bg) }}><b>{c.year}</b> {cell?.name || "—"}<small>{cell?.party || ""}</small></span>; })}
            </div>
          )}
          <p className="muted">{sido.name} 기초단체장(구·시·군의 장) 당선인. 행을 클릭하면 해당 기초자치단체 이력만 봅니다.</p>
          <Matrix data={basic} colLabel="시군구 / 연도" onRow={(r) => setSgg({ code: r.region_code, name: r.region_name })} activeCode={sgg?.code} />
        </>
      )}
      <p className="muted">당선인만 표시(낙선 제외). 출처: 중앙선거관리위원회. 광역·기초단체장 3~8회(2002~2022).</p>
    </>
  );
}
