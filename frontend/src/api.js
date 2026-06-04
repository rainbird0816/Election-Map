const BASE = "/api";

async function get(path, params) {
  const url = new URL(BASE + path, window.location.origin);
  if (params) Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${path} -> ${r.status}`);
  return r.json();
}

export const getElections = () => get("/elections");
export const getMap = (electionId, office = "광역단체장", parent) =>
  get("/map", { election_id: electionId, office, ...(parent ? { parent } : {}) });
export const getRegionHistory = (code, office = "광역단체장") =>
  get(`/region/${code}/history`, { office });
export const getRegionResults = (code, electionId) =>
  get(`/region/${code}/results`, { election_id: electionId });
export const getAssemblyDistrict = (daesu, key) =>
  get("/assembly/district", { daesu, key });
export const getCouncilMap = (hoecha, sgtype, parent) =>
  get("/council/map", { hoecha, sgtype, ...(parent ? { parent } : {}) });
export const getCouncilDetail = (hoecha, sigungu_code) =>
  get("/council/detail", { hoecha, sigungu_code });
export const getPresidentElections = () => get("/president/elections");
export const getPresidentMap = (daesu, parent) =>
  get("/president/map", { daesu, ...(parent ? { parent } : {}) });
export const getPresidentRegion = (daesu, region_code) =>
  get("/president/region", { daesu, region_code });
export const getPresidentHistory = (region_code) =>
  get("/president/history", { region_code });
export const getSummary = (params) => get("/summary", params);
export const getPrecinctLookup = (daesu, sigungu_code, mode) =>
  get("/precinct/lookup", { daesu, sigungu_code, mode });
