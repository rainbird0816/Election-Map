import { useEffect, useMemo, useState } from "react";
import MapKorea from "./maps/MapKorea.jsx";
import MapSigungu from "./maps/MapSigungu.jsx";
import MapDistrict from "./maps/MapDistrict.jsx";
import Legend from "./components/Legend.jsx";
import RegionDetail from "./pages/RegionDetail.jsx";
import AssemblyDistrictDetail from "./pages/AssemblyDistrictDetail.jsx";
import AssemblySidoDetail from "./pages/AssemblySidoDetail.jsx";
import CouncilDetail from "./pages/CouncilDetail.jsx";
import PresidentDetail from "./pages/PresidentDetail.jsx";
import SummaryPanel from "./pages/SummaryPanel.jsx";
import PrecinctLookup from "./pages/PrecinctLookup.jsx";
import SigunguDashboard from "./pages/SigunguDashboard.jsx";
import PrDetail from "./pages/PrDetail.jsx";
import OverviewPage from "./pages/OverviewPage.jsx";
import { getElections, getMap, getCouncilMap, getPresidentElections, getPresidentMap } from "./api";

// 지방의원 데이터가 있는 지선 회차
const COUNCIL_HOECHA = new Set([3, 4, 5, 6, 7, 8]);

// 선거구 경계 지도가 있는 총선 회차 -> {topojson, 당선자, 대수}
const DISTRICT_GEO = {
  122: { topo: "/geo/assembly-22.topo.json", win: "/geo/assembly-22-winners.json", daesu: 22 },
  121: { topo: "/geo/assembly-21.topo.json", win: "/geo/assembly-21-winners.json", daesu: 21 },
};

// 시도 행정표준코드 -> 축약명(geo SIDO 속성과 매칭)
const SIDO_SHORT = {
  "11": "서울", "26": "부산", "27": "대구", "28": "인천", "29": "광주", "30": "대전",
  "31": "울산", "36": "세종", "41": "경기", "42": "강원", "43": "충북", "44": "충남",
  "45": "전북", "46": "전남", "47": "경북", "48": "경남", "50": "제주",
};

export default function App() {
  const [elections, setElections] = useState([]);
  const [presList, setPresList] = useState([]);
  const [daesu, setDaesu] = useState(null);
  const [type, setType] = useState("지선");
  const [electionId, setElectionId] = useState(null);
  const [error, setError] = useState(null);

  const [view, setView] = useState("sido");
  const [sido, setSido] = useState(null);
  const [selected, setSelected] = useState(null);

  const [sidoMap, setSidoMap] = useState([]);
  const [sigunguMap, setSigunguMap] = useState([]);

  // 지선 직책 토글(단체장/교육감/지방의원), 총선 선거구 경계
  const [superView, setSuperView] = useState("단체장");
  const [councilType, setCouncilType] = useState(5); // 5 광역의원 / 6 기초의원
  const [assemblyView, setAssemblyView] = useState("sido");
  const [districtWin, setDistrictWin] = useState(null);
  const [selectedDist, setSelectedDist] = useState(null); // {key, sido, sgg, party, color}

  useEffect(() => {
    getElections().then(setElections).catch((e) => setError(String(e)));
    getPresidentElections().then(setPresList).catch(() => setPresList([]));
  }, []);

  const isPres = type === "대선";
  const byType = useMemo(() => elections.filter((e) => e.type === type), [elections, type]);

  useEffect(() => {
    setView("sido");
    setSido(null);
    setSelected(null);
    setSelectedDist(null);
    setSigunguMap([]);
    setAssemblyView("sido");
    setSuperView("단체장");
    if (isPres) {
      if (presList.length) setDaesu(presList[presList.length - 1].daesu);
    } else if (byType.length) {
      setElectionId(byType[byType.length - 1].id);
    }
  }, [type, byType.length, presList.length]);

  const isCouncil = type === "지선" && superView === "지방의원";
  const isLookup = type === "투표소";
  const isOverview = type === "개관";
  const sidoOffice = type === "총선" ? "국회의원"
    : superView === "교육감" ? "교육감" : "광역단체장";
  const districtConf = type === "총선" ? DISTRICT_GEO[electionId] : null;
  const showDistrict = !!districtConf && assemblyView === "district";
  // 시도별 보기에서 시도 선택 + 경계 데이터 있으면 그 시도 지역구 경계로 줌
  const districtZoom = type === "총선" && assemblyView === "sido" && !!districtConf && !!selected?.code;

  // 시도 지도(지선 광역/지방의원 / 총선 시도집계 / 대선)
  useEffect(() => {
    if (isPres) {
      if (!daesu) return;
      getPresidentMap(daesu).then(setSidoMap).catch((e) => setError(String(e)));
      return;
    }
    if (!electionId) return;
    if (isCouncil) {
      getCouncilMap(electionId, councilType).then(setSidoMap).catch((e) => setError(String(e)));
    } else {
      getMap(electionId, sidoOffice).then(setSidoMap).catch((e) => setError(String(e)));
    }
  }, [electionId, sidoOffice, isCouncil, councilType, isPres, daesu]);

  // 시군구 지도(기초단체장 / 지방의원 / 대선)
  useEffect(() => {
    if (view !== "sigungu" || !sido) return;
    let p;
    if (isPres) {
      if (!daesu) return;
      p = getPresidentMap(daesu, sido.code);
    } else if (!electionId) {
      return;
    } else if (isCouncil) {
      p = getCouncilMap(electionId, councilType, sido.code);
    } else {
      p = getMap(electionId, "기초단체장", sido.code);
    }
    p.then(setSigunguMap).catch(() => setSigunguMap([]));
  }, [electionId, view, sido, isCouncil, councilType, isPres, daesu]);

  // 선거구 당선자 파일
  useEffect(() => {
    if (!districtConf) { setDistrictWin(null); return; }
    fetch(districtConf.win).then((r) => r.json()).then(setDistrictWin).catch(() => setDistrictWin(null));
  }, [districtConf?.win]);

  const sidoColor = useMemo(() => {
    const m = {}; for (const d of sidoMap) m[d.region_code] = d.color_hex; return m;
  }, [sidoMap]);
  const sigunguColor = useMemo(() => {
    const m = {}; for (const d of sigunguMap) m[d.region_code] = d.color_hex; return m;
  }, [sigunguMap]);

  // 선거구 범례용 (정당별 1개)
  const districtLegend = useMemo(() => {
    if (!districtWin) return [];
    const seen = new Map();
    for (const k in districtWin) {
      const w = districtWin[k];
      if (!seen.has(w.party)) seen.set(w.party, { party_name: w.party, color_hex: w.color });
    }
    return [...seen.values()];
  }, [districtWin]);

  // 전국 요약(선거별 평가) 파라미터
  const summaryParams = useMemo(() => {
    if (isPres) return daesu ? { kind: "president", daesu } : null;
    if (type === "총선") return electionId ? { kind: "assembly", election_id: electionId } : null;
    if (isCouncil) return COUNCIL_HOECHA.has(electionId) ? { kind: "council", hoecha: electionId, sgtype: councilType } : null;
    if (type === "지선" && superView === "교육감") return electionId ? { kind: "superintendent", election_id: electionId } : null;
    if (type === "지선") return electionId ? { kind: "local", election_id: electionId, office: "광역단체장" } : null;
    return null;
  }, [isPres, daesu, type, electionId, isCouncil, councilType, superView]);

  function nameOfSido(code) {
    return sidoMap.find((d) => d.region_code === code)?.region_name || code;
  }
  function onSidoClick(code) {
    if (isPres) {
      setSido({ code, name: nameOfSido(code) });
      setView("sigungu");
      setSelected({ code, office: "대통령" });
    } else if (type === "지선" && (superView === "단체장" || (isCouncil && councilType !== 8))) {
      setSido({ code, name: nameOfSido(code) });
      setView("sigungu");
      setSelected(isCouncil ? null : { code, office: "광역단체장" });
    } else {
      setSelected({ code, office: sidoOffice });
      setSelectedDist(null);
    }
  }
  function backToNation() {
    setView("sido"); setSido(null); setSelected(null); setSigunguMap([]);
  }

  return (
    <div className="app">
      <header className="topbar">
        <h1>한국 선거 지도</h1>
        <nav className="tabs">
          {["지선", "총선", "대선", "투표소", "개관"].map((t) => (
            <button key={t} className={`tab ${type === t ? "active" : ""}`} onClick={() => setType(t)}>
              {t === "지선" ? "지방선거" : t === "총선" ? "국회의원" : t === "대선" ? "대통령"
                : t === "투표소" ? "투표소 조회" : "개관"}
            </button>
          ))}
        </nav>
        {type === "지선" && (
          <nav className="tabs subtabs">
            {["단체장", "교육감", "지방의원"].map((v) => (
              <button key={v} className={`tab ${superView === v ? "active" : ""}`} onClick={() => { setSuperView(v); setView("sido"); setSido(null); setSelected(null); setSigunguMap([]); }}>
                {v}
              </button>
            ))}
          </nav>
        )}
        {isCouncil && (
          <nav className="tabs subtabs">
            {[[5, "광역의원"], [6, "기초의원"], [8, "광역비례"], [9, "기초비례"]].map(([v, label]) => (
              <button key={v} className={`tab ${councilType === v ? "active" : ""}`}
                onClick={() => { setCouncilType(v); setView("sido"); setSido(null); setSelected(null); setSigunguMap([]); }}>
                {label}
              </button>
            ))}
          </nav>
        )}
        {type === "총선" && districtConf && (
          <nav className="tabs subtabs">
            {[["sido", "시도별 지역구"], ["district", "전체 지역구 지도"]].map(([v, label]) => (
              <button key={v} className={`tab ${assemblyView === v ? "active" : ""}`} onClick={() => setAssemblyView(v)}>
                {label}
              </button>
            ))}
          </nav>
        )}
        {!isLookup && !isOverview && (
        <div className="selector">
          <label>{type === "지선" ? "회차" : "대수"}&nbsp;</label>
          {isPres ? (
            <select value={daesu ?? ""} onChange={(e) => setDaesu(Number(e.target.value))}>
              {presList.map((e) => (
                <option key={e.daesu} value={e.daesu}>{e.name} ({e.year})</option>
              ))}
            </select>
          ) : (
          <select value={electionId ?? ""} onChange={(e) => setElectionId(Number(e.target.value))}>
            {byType.map((e) => (
              <option key={e.id} value={e.id}>{e.name} ({e.election_date?.slice(0, 4)})</option>
            ))}
          </select>
          )}
        </div>
        )}
      </header>

      {error && <div className="error">백엔드 연결 오류: {error}</div>}

      {isLookup ? <main className="layout single"><PrecinctLookup /></main>
      : isOverview ? <main className="layout single"><OverviewPage /></main> : (
      <>
      <div className="crumbs">
        {isPres ? (
          <>
            <button className="crumb" onClick={backToNation} disabled={view === "sido"}>전국 · 대통령</button>
            {view === "sigungu" && sido && (
              <><span className="sep">›</span><span className="crumb cur">{sido.name}</span></>
            )}
          </>
        ) : type === "지선" && superView === "교육감" ? (
          <span className="crumb cur">전국 · 교육감(성향)</span>
        ) : isCouncil ? (
          <>
            <button className="crumb" onClick={backToNation} disabled={view === "sido"}>
              전국 · {councilType === 5 ? "광역의원" : "기초의원"}
            </button>
            {view === "sigungu" && sido && (
              <><span className="sep">›</span><span className="crumb cur">{sido.name} · 선거구별</span></>
            )}
          </>
        ) : type === "지선" ? (
          <>
            <button className="crumb" onClick={backToNation} disabled={view === "sido"}>전국 · 광역단체장</button>
            {view === "sigungu" && sido && (
              <><span className="sep">›</span><span className="crumb cur">{sido.name} · 기초단체장</span></>
            )}
          </>
        ) : (
          <>
            <button className="crumb" onClick={() => { setSelected(null); setSelectedDist(null); }}
              disabled={showDistrict || !selected?.code}>전국 · 국회의원</button>
            {showDistrict ? (
              <><span className="sep">›</span><span className="crumb cur">전체 지역구 경계</span></>
            ) : selected?.code ? (
              <><span className="sep">›</span><span className="crumb cur">{nameOfSido(selected.code)} 지역구</span></>
            ) : null}
          </>
        )}
      </div>

      <main className="layout">
        <section className="map-pane">
          {showDistrict ? (
            <>
              <MapDistrict
                geoUrl={districtConf.topo}
                winners={districtWin}
                selectedKey={selectedDist?.key}
                onSelect={(key, props, w) =>
                  setSelectedDist({ key, sido: props.SIDO, sgg: props.SGG, party: w?.party, color: w?.color, name: w?.name })}
              />
              <Legend mapData={districtLegend} />
            </>
          ) : districtZoom ? (
            <>
              <MapDistrict
                geoUrl={districtConf.topo}
                winners={districtWin}
                sidoFilter={SIDO_SHORT[selected.code]}
                selectedKey={selectedDist?.key}
                onSelect={(key, props, w) =>
                  setSelectedDist({ key, sido: props.SIDO, sgg: props.SGG, party: w?.party, color: w?.color, name: w?.name })}
              />
              <Legend mapData={districtLegend} />
            </>
          ) : view === "sido" ? (
            <>
              <MapKorea colorByCode={sidoColor} selectedCode={selected?.code} onSelect={onSidoClick} />
              <Legend mapData={sidoMap} />
            </>
          ) : (
            <>
              <MapSigungu
                sidoCode={sido.code}
                electionId={isPres ? null : electionId}
                colorByCode={sigunguColor}
                selectedCode={selected?.code}
                onSelect={(code) => setSelected({ code, office: isPres ? "대통령" : isCouncil ? "지방의원" : "기초단체장" })}
              />
              <Legend mapData={sigunguMap} />
              {sigunguMap.length === 0 && (
                <p className="hint">이 시도의 {isPres ? "대선" : isCouncil ? "지방의원" : "기초단체장"} 데이터가 없습니다.</p>
              )}
            </>
          )}
        </section>

        {showDistrict ? (
          <aside className="detail">
            {selectedDist ? (
              <>
                <h2>{selectedDist.sido} {selectedDist.sgg} <span className="office-badge">지역구</span></h2>
                <div className="winner-card" style={{ borderLeftColor: selectedDist.color }}>
                  <div className="wc-label">당선자</div>
                  <div className="wc-name">{selectedDist.name || "—"}</div>
                  <div className="wc-party" style={{ color: selectedDist.color }}>{selectedDist.party}</div>
                </div>
                <AssemblyDistrictDetail daesu={districtConf.daesu} dkey={selectedDist.key} />
              </>
            ) : (
              <div className="detail empty">선거구를 클릭하세요.</div>
            )}
          </aside>
        ) : isPres ? (
          <aside className="detail">
            {selected?.code ? (
              <PresidentDetail
                daesu={daesu}
                code={selected.code}
                name={sigunguMap.find((d) => d.region_code === selected.code)?.region_name
                  || sidoMap.find((d) => d.region_code === selected.code)?.region_name || "지역"}
              />
            ) : (
              <SummaryPanel params={summaryParams} label="시도를 클릭하면 후보별 득표·시군구·역대 추이가 보입니다." />
            )}
          </aside>
        ) : isCouncil && councilType === 9 && view === "sigungu" && selected?.code && selected.code.length > 2 ? (
          <PrDetail hoecha={electionId} sgtype={9} sigungu={selected.code} />
        ) : isCouncil && councilType === 8 ? (
          selected?.code ? (
            <PrDetail hoecha={electionId} sgtype={8} sido={selected.code} />
          ) : (
            <aside className="detail">
              <SummaryPanel params={summaryParams} label="시도를 클릭하면 그 시도의 광역비례 의석·당선자가 보입니다." />
            </aside>
          )
        ) : type === "지선" && view === "sigungu" && selected?.code && selected.code.length > 2 ? (
          <SigunguDashboard
            hoecha={electionId}
            sggCode={selected.code}
            sggName={sigunguMap.find((d) => d.region_code === selected.code)?.region_name || "시군구"}
            sidoCode={sido?.code}
            sidoName={sido?.name}
          />
        ) : isCouncil ? (
          <aside className="detail">
            {view === "sigungu" && selected?.code ? (
              <CouncilDetail
                hoecha={electionId}
                code={selected.code}
                name={sigunguMap.find((d) => d.region_code === selected.code)?.region_name || "선거구"}
              />
            ) : COUNCIL_HOECHA.has(electionId) ? (
              <SummaryPanel
                params={view === "sigungu" && sido?.code
                  ? { kind: "council", hoecha: electionId, sgtype: councilType, sido: sido.code }
                  : summaryParams}
                label={view === "sigungu"
                  ? `${sido?.name} · 시군구를 클릭하면 선거구별 결과가 보입니다.`
                  : "시도를 클릭하면 그 시도 요약이, 시군구를 클릭하면 상세가 보입니다."} />
            ) : (
              <div className="detail empty">이 회차의 지방의원 데이터는 아직 없습니다.</div>
            )}
          </aside>
        ) : type === "총선" ? (
          selectedDist ? (
            <aside className="detail">
              <h2>{selectedDist.sido} {selectedDist.sgg} <span className="office-badge">지역구</span></h2>
              <div className="winner-card" style={{ borderLeftColor: selectedDist.color }}>
                <div className="wc-label">당선자</div>
                <div className="wc-name">{selectedDist.name || "—"}</div>
                <div className="wc-party" style={{ color: selectedDist.color }}>{selectedDist.party}</div>
              </div>
              <AssemblyDistrictDetail daesu={districtConf.daesu} dkey={selectedDist.key} />
            </aside>
          ) : selected?.code ? (
            <AssemblySidoDetail daesu={electionId - 100} sido={selected.code} sidoName={nameOfSido(selected.code)} />
          ) : (
            <aside className="detail">
              <SummaryPanel params={summaryParams} label="시도를 클릭하면 그 시도의 지역구별 결과가 보입니다." />
            </aside>
          )
        ) : selected?.code ? (
          <RegionDetail code={selected.code} electionId={electionId} office={selected.office || sidoOffice} />
        ) : (
          <aside className="detail">
            <SummaryPanel params={summaryParams} label="시도를 클릭하면 지역 상세가 보입니다." />
          </aside>
        )}
      </main>
      </>
      )}
    </div>
  );
}
