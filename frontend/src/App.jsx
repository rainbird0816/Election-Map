import { useEffect, useMemo, useState } from "react";
import MapKorea from "./maps/MapKorea.jsx";
import MapSigungu from "./maps/MapSigungu.jsx";
import MapDistrict from "./maps/MapDistrict.jsx";
import ByelectionMap from "./maps/ByelectionMap.jsx";
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
import PoliticianPage from "./pages/PoliticianPage.jsx";
import ByElectionPage from "./pages/ByElectionPage.jsx";
import WinnersPage from "./pages/WinnersPage.jsx";
import MetroDashboard from "./pages/MetroDashboard.jsx";
import BasicDashboard from "./pages/BasicDashboard.jsx";
import CouncilSeatsPanel from "./components/CouncilSeatsPanel.jsx";
import { getElections, getMap, getCouncilMap, getMetroSggMap, getBasicSidoMap, getPresidentElections, getPresidentMap, getByelectionDates, getByelectionRoundMap } from "./api";

// 지방의회 데이터 보유 회차 — 의원 유형별(council 테이블 실측 기준)
// 광역의원·광역비례는 1회(1995)부터, 기초의원은 3회(2002)부터, 기초비례는 4회(2006, 1인2표)부터.
const COUNCIL_HOECHA = {
  5: new Set([1, 2, 3, 4, 5, 6, 7, 8, 9]), // 광역의원
  8: new Set([1, 2, 3, 4, 5, 6, 7, 8, 9]), // 광역비례
  6: new Set([3, 4, 5, 6, 7, 8, 9]),       // 기초의원
  9: new Set([4, 5, 6, 7, 8, 9]),          // 기초비례
};
const councilHas = (sgtype, hoecha) => !!COUNCIL_HOECHA[sgtype]?.has(hoecha);
const COUNCIL_LABEL = { 5: "광역의원", 6: "기초의원", 8: "광역비례", 9: "기초비례" };

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
  const [type, setType] = useState("개관");
  const [electionId, setElectionId] = useState(null);
  const [error, setError] = useState(null);

  const [view, setView] = useState("sido");
  const [sido, setSido] = useState(null);
  const [selected, setSelected] = useState(null);

  const [sidoMap, setSidoMap] = useState([]);
  const [sigunguMap, setSigunguMap] = useState([]);

  // 지선 직책 토글(단체장/교육감/지방의원), 총선 선거구 경계
  const [superView, setSuperView] = useState("광역종합");
  const [councilType, setCouncilType] = useState(5); // 5 광역의원 / 6 기초의원
  const [assemblyView, setAssemblyView] = useState("sido");
  const [districtWin, setDistrictWin] = useState(null);
  const [selectedDist, setSelectedDist] = useState(null); // {key, sido, sgg, party, color}
  const [byeDate, setByeDate] = useState(null);   // 단체장 탭에서 선택한 보궐 선거일(null=정규 회차)
  const [byeDates, setByeDates] = useState([]);   // 현재 직책의 보궐 선거일 목록(셀렉터용)

  useEffect(() => {
    getElections().then(setElections).catch((e) => setError(String(e)));
    getPresidentElections().then(setPresList).catch(() => setPresList([]));
  }, []);

  const isPres = type === "대선";
  const byType = useMemo(() => elections.filter((e) => e.type === type), [elections, type]);

  // 선택 선거의 연도 → 2023.7 군위군 대구 편입 이후면 지도에 편입 반영
  const electionYear = useMemo(() => {
    if (byeDate) return Number(byeDate.slice(0, 4));
    if (isPres) return presList.find((e) => e.daesu === daesu)?.year ?? null;
    const y = byType.find((e) => e.id === electionId)?.election_date?.slice(0, 4);
    return y ? Number(y) : null;
  }, [byeDate, isPres, presList, daesu, byType, electionId]);
  const mergeGunwi = electionYear != null && electionYear >= 2023;
  // 인천 2026-07-01 자치구 개편(검단/영종/제물포 신설) — 9회 지선(2026)부터 신 경계
  const incheon2026 = electionYear != null && electionYear >= 2026;
  // 세종시 출범(2012-07-01) 이전 → 그 지역은 충남 연기군. 지도·라벨을 연기군으로 표기
  const mergeSejong = electionYear != null && electionYear < 2012;
  // 계룡시 출범(2003-09-19) 이전 → 그 지역은 논산. 1·2·3회는 계룡 폴리곤을 논산에 귀속
  const mergeGyeryong = electionYear != null && electionYear < 2003;

  useEffect(() => {
    setView("sido");
    setSido(null);
    setSelected(null);
    setSelectedDist(null);
    setSigunguMap([]);
    setAssemblyView("sido");
    setSuperView("광역종합");
    if (isPres) {
      if (presList.length) setDaesu(presList[presList.length - 1].daesu);
    } else if (byType.length) {
      setElectionId(byType[byType.length - 1].id);
    }
  }, [type, byType.length, presList.length]);

  // 단체장·교육감·지방의회 탭이면 그 직책 보궐 선거일을 셀렉터에 끼움. 탭을 벗어나면 보궐 해제.
  useEffect(() => {
    setByeDate(null);
    let office = null;
    if (type === "총선") office = "국회의원";
    else if (type === "지선") {
      if (superView === "교육감") office = "교육감";
      else if (superView === "단체장") office = "광역단체장";
      else if (superView === "의원" && councilType === 5) office = "광역의원";
      else if (superView === "의원" && councilType === 6) office = "기초의원";
    }
    if (office) getByelectionDates(office).then(setByeDates).catch(() => setByeDates([]));
    else setByeDates([]);
  }, [type, superView, councilType]);

  const isCouncil = type === "지선" && superView === "의원";
  const isMetroSummary = type === "지선" && superView === "광역종합";
  const isBasicSummary = type === "지선" && superView === "기초종합";
  const isDanche = type === "지선" && superView === "단체장";   // 단체장 탭(보궐 회차 지원)
  // 보궐 회차 지원 직책. 단체장·교육감=시도지도, 광역/기초의원·국회의원=시군구 국가지도.
  const byeOffice = type === "총선" ? "국회의원"
    : type !== "지선" ? null
    : superView === "교육감" ? "교육감"
    : superView === "단체장" ? "광역단체장"
    : (superView === "의원" && councilType === 5) ? "광역의원"
    : (superView === "의원" && councilType === 6) ? "기초의원" : null;
  const canBye = !!byeOffice;
  const byeIsSigungu = byeOffice === "광역의원" || byeOffice === "기초의원" || byeOffice === "국회의원";
  const isLookup = type === "투표소";
  const isOverview = type === "개관";
  const isByelection = type === "보궐";
  const isWinners = type === "당선인";
  const isPolitician = type === "정치인";
  const sidoOffice = type === "총선" ? "국회의원"
    : superView === "교육감" ? "교육감" : "광역단체장";
  const districtConf = type === "총선" && !byeDate ? DISTRICT_GEO[electionId] : null;
  const showDistrict = !!districtConf && assemblyView === "district";
  // 시도별 보기에서 시도 선택 + 경계 데이터 있으면 그 시도 지역구 경계로 줌
  const districtZoom = type === "총선" && !byeDate && assemblyView === "sido" && !!districtConf && !!selected?.code;

  // 시도 지도(지선 광역/지방의원 / 총선 시도집계 / 대선)
  useEffect(() => {
    if (isPres) {
      if (!daesu) return;
      getPresidentMap(daesu).then(setSidoMap).catch((e) => setError(String(e)));
      return;
    }
    if (byeDate) {   // 보궐 회차: 보궐 지역 진하게 + 직전 기준 옅게(단체장 시도 / 의회 시군구)
      getByelectionRoundMap(byeOffice, byeDate).then(setSidoMap).catch(() => setSidoMap([]));
      return;
    }
    if (!electionId) return;
    if (isCouncil) {
      getCouncilMap(electionId, councilType).then(setSidoMap).catch((e) => setError(String(e)));
    } else if (isBasicSummary) {
      // 기초 종합 전국지도는 그 회차 광역단체장(시도지사) 당선 정당색으로 채색
      getMap(electionId, "광역단체장").then(setSidoMap).catch((e) => setError(String(e)));
    } else {
      getMap(electionId, sidoOffice).then(setSidoMap).catch((e) => setError(String(e)));
    }
  }, [electionId, sidoOffice, isCouncil, isBasicSummary, councilType, isPres, daesu, byeDate, byeOffice]);

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
    } else if (isMetroSummary) {
      p = getMetroSggMap(electionId, sido.code);
    } else if (byeDate && isDanche) {   // 단체장 보궐 회차: 그 시도 기초단체장 보궐 진하게 + 직전 옅게
      p = getByelectionRoundMap("기초단체장", byeDate, sido.code);
    } else {
      p = getMap(electionId, "기초단체장", sido.code);
    }
    p.then(setSigunguMap).catch(() => setSigunguMap([]));
  }, [electionId, view, sido, isCouncil, isMetroSummary, councilType, isPres, daesu, byeDate]);

  // 선거구 당선자 파일
  useEffect(() => {
    if (!districtConf) { setDistrictWin(null); return; }
    fetch(districtConf.win).then((r) => r.json()).then(setDistrictWin).catch(() => setDistrictWin(null));
  }, [districtConf?.win]);

  const sidoColor = useMemo(() => {
    const m = {}; for (const d of sidoMap) m[d.region_code] = d.color_hex;
    // 9회 전남광주통합특별시(49): 통합 경계 대신 광주(29)·전남(46) 양쪽을 통합시 당선색으로 채색
    if (m["49"]) { m["29"] = m["49"]; m["46"] = m["49"]; }
    return m;
  }, [sidoMap]);
  const sigunguColor = useMemo(() => {
    const m = {}; for (const d of sigunguMap) m[d.region_code] = d.color_hex; return m;
  }, [sigunguMap]);
  // 보궐 회차에서 클릭한 지역의 round-map 행(보궐 당선 or 직전 옅게)
  const byeSel = byeDate && selected?.code
    ? (sigunguMap.find((d) => d.region_code === selected.code)
      || sidoMap.find((d) => d.region_code === selected.code))
    : null;

  // 회차 셀렉터: 정규 선거 + 보궐을 연도(날짜)순으로 섞어 표시. 같은 해 보궐 2회↑면 날짜순 번호.
  const selectorOptions = useMemo(() => {
    if (isPres) return [];
    const kind = type === "총선" ? "국회의원선거" : "전국동시지방선거";
    const reg = byType.map((e) => {
      const ord = type === "총선" ? `제${e.id - 100}대` : `제${e.id}회`;
      return {
        key: `r${e.id}`, value: String(e.id), date: e.election_date || "",
        label: `${(e.election_date || "").slice(0, 4)} ${ord} ${kind}`,
      };
    });
    const byYear = {};
    for (const b of byeDates) (byYear[b.date.slice(0, 4)] ||= []).push(b.date);
    const bye = byeDates.map((b) => {
      const yr = b.date.slice(0, 4);
      const lst = byYear[yr];
      const n = lst.length > 1 ? ` ${lst.indexOf(b.date) + 1}` : "";
      return { key: `b${b.date}`, value: `b:${b.date}`, date: b.date, label: `${yr} 재·보궐선거${n}` };
    });
    return [...reg, ...bye].sort((a, b) => a.date.localeCompare(b.date));
  }, [isPres, type, byType, byeDates]);

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
    if (isCouncil) return councilHas(councilType, electionId) ? { kind: "council", hoecha: electionId, sgtype: councilType } : null;
    if (type === "지선" && superView === "교육감") return electionId ? { kind: "superintendent", election_id: electionId } : null;
    if (type === "지선") return electionId ? { kind: "local", election_id: electionId, office: superView === "기초종합" ? "기초단체장" : "광역단체장" } : null;
    return null;
  }, [isPres, daesu, type, electionId, isCouncil, councilType, superView]);

  function nameOfSido(code) {
    // 9회 통합 채색 시 sidoMap엔 49(통합시)만 있어 광주(29)·전남(46)은 미발견 → SIDO_SHORT fallback
    return sidoMap.find((d) => d.region_code === code)?.region_name || SIDO_SHORT[code] || code;
  }
  function onSidoClick(code) {
    if (isPres) {
      setSido({ code, name: nameOfSido(code) });
      setView("sigungu");
      setSelected({ code, office: "대통령" });
    } else if (type === "지선" && (isMetroSummary || isBasicSummary || superView === "단체장" || (isCouncil && councilType !== 8))) {
      setSido({ code, name: nameOfSido(code) });
      setView("sigungu");
      setSelected(isCouncil || isMetroSummary || isBasicSummary ? null : { code, office: "광역단체장" });
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
          {["개관", "대선", "총선", "지선", "보궐", "당선인", "투표소", "정치인"].map((t) => (
            <button key={t} className={`tab ${type === t ? "active" : ""}`} onClick={() => setType(t)}>
              {t === "지선" ? "지방선거" : t === "총선" ? "국회의원" : t === "대선" ? "대통령"
                : t === "보궐" ? "재보궐" : t === "당선인" ? "당선인" : t === "투표소" ? "투표소 조회"
                : t === "정치인" ? "정치인" : "개관"}
            </button>
          ))}
        </nav>
        {type === "지선" && (
          <nav className="tabs subtabs">
            {[["광역종합", "광역 종합"], ["기초종합", "기초 종합"], ["단체장", "단체장"], ["교육감", "교육감"], ["의원", "지방의회"]].map(([v, label]) => (
              <button key={v} className={`tab ${superView === v ? "active" : ""}`} onClick={() => { setSuperView(v); setView("sido"); setSido(null); setSelected(null); setSigunguMap([]); }}>
                {label}
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
        {!isLookup && !isOverview && !isByelection && !isWinners && !isPolitician && (
        <div className="selector">
          <label>{type === "지선" ? "회차" : "대수"}&nbsp;</label>
          {isPres ? (
            <select value={daesu ?? ""} onChange={(e) => setDaesu(Number(e.target.value))}>
              {presList.map((e) => (
                <option key={e.daesu} value={e.daesu}>{e.name} ({e.year})</option>
              ))}
            </select>
          ) : (
          <select
            value={byeDate ? `b:${byeDate}` : (electionId ?? "")}
            onChange={(e) => {
              const v = e.target.value;
              if (v.startsWith("b:")) { setByeDate(v.slice(2)); }
              else { setByeDate(null); setElectionId(Number(v)); }
            }}>
            {selectorOptions.map((o) => (
              <option key={o.key} value={o.value}>{o.label}</option>
            ))}
          </select>
          )}
        </div>
        )}
      </header>

      {error && <div className="error">백엔드 연결 오류: {error}</div>}

      {isLookup ? <main className="layout single"><PrecinctLookup /></main>
      : isOverview ? <main className="layout single"><OverviewPage /></main>
      : isByelection ? <main className="layout single"><ByElectionPage /></main>
      : isWinners ? <main className="layout single"><WinnersPage /></main>
      : isPolitician ? <main className="layout single"><PoliticianPage /></main> : (
      <>
      <div className="crumbs">
        {isPres ? (
          <>
            <button className="crumb" onClick={backToNation} disabled={view === "sido"}>전국 · 대통령</button>
            {view === "sigungu" && sido && (
              <><span className="sep">›</span><span className="crumb cur">{sido.name}</span></>
            )}
          </>
        ) : isMetroSummary ? (
          <>
            <button className="crumb" onClick={backToNation} disabled={view === "sido"}>전국 · 광역단체장</button>
            {view === "sigungu" && sido && (
              <>
                <span className="sep">›</span>
                <button className="crumb" onClick={() => setSelected(null)} disabled={!selected?.code}>{sido.name}</button>
                {selected?.code && (
                  <><span className="sep">›</span><span className="crumb cur">{sigunguMap.find((d) => d.region_code === selected.code)?.region_name || "시군구"}</span></>
                )}
              </>
            )}
          </>
        ) : isBasicSummary ? (
          <>
            <button className="crumb" onClick={backToNation} disabled={view === "sido"}>전국 · 기초단체장</button>
            {view === "sigungu" && sido && (
              <>
                <span className="sep">›</span>
                <button className="crumb" onClick={() => setSelected(null)} disabled={!selected?.code}>{sido.name}</button>
                {selected?.code && (
                  <><span className="sep">›</span><span className="crumb cur">{sigunguMap.find((d) => d.region_code === selected.code)?.region_name || "시군구"}</span></>
                )}
              </>
            )}
          </>
        ) : type === "지선" && superView === "교육감" ? (
          <span className="crumb cur">전국 · 교육감(성향)</span>
        ) : isCouncil ? (
          <>
            <button className="crumb" onClick={backToNation} disabled={view === "sido"}>
              전국 · {COUNCIL_LABEL[councilType]}
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
          {(byeDate && byeIsSigungu) ? (
            <>
              <ByelectionMap level="sigungu" colorByCode={sidoColor}
                selectedCode={selected?.code} onSelect={(code) => setSelected({ code })} />
              <Legend mapData={sidoMap} />
            </>
          ) : showDistrict ? (
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
              <MapKorea colorByCode={sidoColor} selectedCode={selected?.code} onSelect={onSidoClick} mergeGunwi={mergeGunwi} mergeSejong={mergeSejong} />
              <Legend mapData={sidoMap} />
            </>
          ) : (
            <>
              <MapSigungu
                sidoCode={sido.code}
                electionId={isPres ? null : electionId}
                electionYear={electionYear}
                colorByCode={sigunguColor}
                selectedCode={selected?.code}
                mergeGunwi={mergeGunwi}
                mergeSejong={mergeSejong}
                mergeGyeryong={mergeGyeryong}
                incheon2026={incheon2026}
                onSelect={(code) => setSelected({ code, office: isPres ? "대통령" : isCouncil ? "지방의원" : isMetroSummary ? "광역단체장" : "기초단체장" })}
              />
              <Legend mapData={sigunguMap} />
              {sigunguMap.length === 0 && (
                <p className="hint">이 시도의 {isPres ? "대선" : isCouncil ? "지방의원" : isMetroSummary ? "광역단체장" : "기초단체장"} 데이터가 없습니다.</p>
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
        ) : byeDate ? (
          <aside className="detail">
            <h2>{byeSel?.region_name || (selected?.code && nameOfSido(selected.code)) || "재·보궐"} <span className="office-badge">{byeOffice} 보궐 {byeDate}</span></h2>
            {byeSel ? (byeSel.faded ? (
              <p className="muted">이 지역은 {byeDate} 보궐선거가 없었습니다. 지도색은 직전 정규선거 {byeIsSigungu ? "다수당" : "당선자"}(<b>{byeSel.winner_party}</b>)을 옅게 표시한 것입니다.</p>
            ) : (
              <div className="winner-card" style={{ borderLeftColor: byeSel.color_hex }}>
                <div className="wc-label">{byeSel.winner_party === "경합" ? "보궐(같은날 분할)" : "보궐 당선"}</div>
                <div className="wc-name">{byeSel.winner_party === "경합" ? "경합" : byeSel.winner_name}</div>
                <div className="wc-party" style={{ color: byeSel.color_hex }}>{byeSel.winner_party}</div>
              </div>
            )) : <p className="muted">지도에서 지역을 클릭하면 보궐/직전 당선자가 보입니다.</p>}
            <p className="muted">진한 색 = {byeDate} 보궐 당선 정당{isDanche
              ? " · 옅은 색 = 직전 정규선거 당선자. 시도 클릭 시 기초단체장 보궐도 표시."
              : byeOffice === "국회의원" ? " (직전 정규 데이터 없이 보궐 지역만 표시)"
              : byeIsSigungu ? " · 옅은 색 = 직전 정규선거 다수당"
              : " (교육감은 직전 정규 데이터가 없어 보궐 지역만)"}.</p>
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
        ) : isMetroSummary ? (
          view === "sigungu" && sido ? (
            <MetroDashboard
              hoecha={electionId}
              sidoCode={sido.code}
              sidoName={sido.name}
              sggCode={selected?.code && selected.code.length > 2 ? selected.code : undefined}
              sggName={selected?.code ? (sigunguMap.find((d) => d.region_code === selected.code)?.region_name || "시군구") : undefined}
            />
          ) : (
            <aside className="detail">
              <SummaryPanel params={summaryParams} label="시도를 클릭하면 그 시도의 광역 종합(도지사·광역의회·광역비례)이 보입니다." />
            </aside>
          )
        ) : isBasicSummary ? (
          view === "sigungu" && sido && selected?.code && selected.code.length > 2 ? (
            <SigunguDashboard
              hoecha={electionId}
              sggCode={selected.code}
              sggName={sigunguMap.find((d) => d.region_code === selected.code)?.region_name || "시군구"}
              sidoCode={sido.code}
              sidoName={sido.name}
            />
          ) : view === "sigungu" && sido ? (
            <BasicDashboard hoecha={electionId} sidoCode={sido.code} sidoName={sido.name} />
          ) : (
            <aside className="detail">
              <SummaryPanel params={summaryParams} label="시도를 클릭하면 기초단체장 분포가, 기초를 클릭하면 그 기초의 종합이 보입니다." />
            </aside>
          )
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
            {!councilHas(councilType, electionId) ? (
              <div className="detail empty">이 회차의 {COUNCIL_LABEL[councilType]} 데이터는 아직 없습니다.</div>
            ) : view === "sigungu" && sido?.code ? (
              <>
                <h2>{sido.name} <span className="office-badge">광역의회</span></h2>
                <CouncilSeatsPanel hoecha={electionId} level="metro" sido={sido.code} heading={false} />
                <p className="muted">시군구를 클릭하면 그 기초자치단체 종합(기초의회 포함)이 보입니다.</p>
              </>
            ) : (
              <SummaryPanel params={summaryParams} label="시도를 클릭하면 광역의회, 시군구를 클릭하면 기초의회 의석분포가 보입니다." />
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
