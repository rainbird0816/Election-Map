import { useEffect, useMemo, useState } from "react";
import { getByelectionMap, getByelectionRegion } from "../api";
import ByelectionMap from "../maps/ByelectionMap.jsx";

const fmt = (n) => (n == null ? "—" : Number(n).toLocaleString());

// 직책 분류 → 하위(단체장/의원) → sgtype. 광역단체장3·시도의원5·기초단체장4·구시군의원6·국회의원2·교육감11.
const CATS = [
  { key: "광역", subs: [["단체장", 3], ["의원", 5]] },
  { key: "기초", subs: [["단체장", 4], ["의원", 6]] },
  { key: "국회의원", subs: [["", 2]] },
  { key: "교육감", subs: [["", 11]] },
];
const isSido = (sgt) => sgt === 3 || sgt === 11;

export default function ByElectionPage() {
  const [cat, setCat] = useState(0);
  const [sub, setSub] = useState(0);
  const [mapData, setMapData] = useState(null);
  const [sel, setSel] = useState(null);     // {code, name}
  const [detail, setDetail] = useState(null);

  const subs = CATS[cat].subs;
  const sgtype = subs[Math.min(sub, subs.length - 1)][1];
  const level = isSido(sgtype) ? "sido" : "sigungu";

  useEffect(() => {
    setMapData(null); setSel(null); setDetail(null);
    getByelectionMap(sgtype).then(setMapData).catch(() => setMapData([]));
  }, [sgtype]);

  useEffect(() => {
    setDetail(null);
    if (!sel) return;
    getByelectionRegion(sgtype, sel.code).then(setDetail).catch(() => setDetail([]));
  }, [sel, sgtype]);

  const colorByCode = useMemo(() => {
    const m = {};
    for (const d of mapData || []) m[d.region_code] = d.color_hex;
    return m;
  }, [mapData]);

  const totalSeats = (mapData || []).reduce((a, d) => a + d.count, 0);
  const selRow = mapData?.find((d) => d.region_code === sel?.code);

  return (
    <div className="lookup-page bye-page">
      <h2>재·보궐선거</h2>
      <p className="muted">
        전국동시선거(대선·총선·지선) 외에 치러진 재·보궐선거를 직책별로 모았습니다.
        지도에서 보궐이 있었던 지역만 당선 정당색으로 칠해지며, 클릭하면 그 지역의 회차별 후보(낙선 포함)가 보입니다.
        출처: 중앙선거관리위원회.
      </p>

      {/* 직책 분류 탭 */}
      <nav className="tabs subtabs bye-cats">
        {CATS.map((c, i) => (
          <button key={c.key} className={`tab ${i === cat ? "active" : ""}`}
            onClick={() => { setCat(i); setSub(0); }}>{c.key}</button>
        ))}
      </nav>
      {/* 하위(단체장/의원) — 광역·기초만 */}
      {subs.length > 1 && (
        <div className="seg bye-subs">
          {subs.map(([label], i) => (
            <button key={label} className={`seg-btn ${i === sub ? "active" : ""}`}
              onClick={() => setSub(i)}>{label}</button>
          ))}
        </div>
      )}

      <div className="bye-maplayout">
        {/* 지도 */}
        <section className="bye-map">
          {!mapData ? <div className="map-loading">불러오는 중…</div>
            : !mapData.length ? <p className="hint">이 직책의 보궐선거 데이터가 없습니다.</p> : (
            <ByelectionMap level={level} colorByCode={colorByCode}
              selectedCode={sel?.code} onSelect={(code, name) => setSel({ code, name })} />
          )}
          {mapData?.length > 0 && (
            <p className="muted bye-mapnote">
              {mapData.length}개 {isSido(sgtype) ? "시·도" : "시·군·구"} · 당선 {totalSeats}명 · 색=최다 승리 정당(계열), 동률은 경합(회색)
            </p>
          )}
        </section>

        {/* 우측: 선택 지역 상세 또는 지역 목록 */}
        <aside className="detail">
          {sel ? (
            <>
              <h2>{selRow?.region_name || sel.name} <span className="office-badge">{CATS[cat].key}{subs.length > 1 ? " " + subs[sub][0] : ""} 보궐</span></h2>
              {!detail ? <p className="muted">불러오는 중…</p>
                : detail.length === 0 ? <p className="hint">데이터가 없습니다.</p>
                : detail.map((r, i) => (
                  <div key={i} className="bye-racecard">
                    <div className="bye-racehead">
                      <span className="yr term">{r.vote_date}</span>
                      <span className="bye-region">{r.sgg}</span>
                    </div>
                    <table className="cand-table">
                      <tbody>
                        {r.candidates.map((c, j) => (
                          <tr key={j} className={c.elected ? "elected-row" : ""}>
                            <td><span className="dot" style={{ background: c.color_hex }} /></td>
                            <td>{c.name}{c.elected ? <span className="win-tag">당선</span> : null}</td>
                            <td>{c.party}</td>
                            <td className="num">{fmt(c.votes)}</td>
                            <td className="num">{c.rate == null ? "무투표" : `${c.rate}%`}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ))}
              <button className="link-btn" onClick={() => setSel(null)}>← 전체 목록</button>
            </>
          ) : (
            <>
              <h2>{CATS[cat].key}{subs.length > 1 ? " " + subs[sub][0] : ""} 보궐 <span className="office-badge">{(mapData || []).length}곳</span></h2>
              {!mapData ? <p className="muted">불러오는 중…</p>
                : mapData.length === 0 ? <p className="muted">데이터 없음</p> : (
                <ul className="bye-reglist">
                  {mapData.map((d) => (
                    <li key={d.region_code}>
                      <button className="bye-regrow" onClick={() => setSel({ code: d.region_code, name: d.region_name })}>
                        <span className="dot" style={{ background: d.color_hex }} />
                        <span className="bye-regnm">{d.region_name}</span>
                        <span className="bye-regwin">
                          {d.count > 1
                            ? <b style={{ color: d.tie ? "#777" : d.color_hex }}>{d.tie ? "경합" : `${d.winner_party} 최다`}</b>
                            : <>{d.winner_name}<span className="bye-party"> {d.winner_party}</span></>}
                        </span>
                        {d.count > 1 && <span className="bye-cnt">{d.count}건</span>}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              <p className="muted">지도 또는 목록에서 지역을 선택하세요.</p>
            </>
          )}
        </aside>
      </div>
    </div>
  );
}
