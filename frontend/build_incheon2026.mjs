// 인천 2026-07-01 행정구역 개편 → 행정동 경계를 신 자치구로 합성(dissolve).
// 입력: data/raw/incheon_dong.geojson (행정동 경계, raqoon886/Local_HangJeongDong)
// 출력: public/geo/incheon-2026.geo.json (11개 자치구, 코드=korea-sigungu 23xx 체계)
import fs from "fs";
import { topology } from "topojson-server";
import { merge } from "topojson-client";

const SRC = "../data/raw/incheon_dong.geojson";
const OUT = "public/geo/incheon-2026.geo.json";

// 신 자치구 ← 행정동(adm_nm의 동 부분). 명시 안 한 구(계양/남동/미추홀/부평/연수/강화/옹진)는 통째로 유지.
const DONG2GU = {
  // 영종구 ← 중구 도서부
  영종구: ["영종동", "영종1동", "운서동", "용유동"],
  // 제물포구 ← 중구 육지부 + 동구 전역
  제물포구: ["연안동", "신포동", "신흥동", "도원동", "율목동", "동인천동", "북성동", "송월동",
    "만석동", "화수1·화평동", "화수2동", "송현1·2동", "송현3동",
    "송림1동", "송림2동", "송림3·5동", "송림4동", "송림6동", "금창동"],
  // 검단구 ← 서구 검단지역
  검단구: ["불로대곡동", "원당동", "마전동", "검단동", "오류왕길동", "당하동"],
};
// 구 단위 유지(미개편) — adm_nm의 구 이름 → korea-sigungu 코드/표시명
const KEEP_GU = {
  계양구: "23070", 남동구: "23050", 미추홀구: "23030", 부평구: "23060",
  연수구: "23040", 강화군: "23310", 옹진군: "23320",
};
// 신/잔존 구 코드
const GU_CODE = { 검단구: "23090", 영종구: "23100", 제물포구: "23110", 서구: "23080", ...KEEP_GU };

const dong2gu = {};
for (const [gu, dongs] of Object.entries(DONG2GU)) for (const d of dongs) dong2gu[d] = gu;

const fc = JSON.parse(fs.readFileSync(SRC, "utf-8"));
// 각 feature에 목표 구(targetGu) 라벨링
const labeled = [];
for (const f of fc.features) {
  const [, gu, ...rest] = f.properties.adm_nm.split(" ");
  const dong = rest.join(" ");
  let target;
  if (gu === "중구" || gu === "동구" || gu === "서구") {
    target = dong2gu[dong] || (gu === "서구" ? "서구" : null); // 중/동구 잔여는 모두 제물포로 매핑됐어야 함
    if (!target) { console.error("미분류 동:", gu, dong); process.exit(1); }
  } else {
    target = gu; // 미개편 구 그대로
  }
  labeled.push({ ...f, properties: { gu: target } });
}

// 구별로 묶어 dissolve
const byGu = {};
for (const f of labeled) (byGu[f.properties.gu] ||= []).push(f);

const features = [];
for (const [gu, feats] of Object.entries(byGu)) {
  const topo = topology({ g: { type: "FeatureCollection", features: feats } });
  const geom = merge(topo, topo.objects.g.geometries);
  const code = GU_CODE[gu];
  if (!code) { console.error("코드 없는 구:", gu); process.exit(1); }
  features.push({ type: "Feature", properties: { code, name: gu }, geometry: geom });
  console.log(`${gu} [${code}] ← ${feats.length}개 동`);
}

fs.writeFileSync(OUT, JSON.stringify({ type: "FeatureCollection", features }));
console.log(`\nwrote ${OUT} (${features.length}개 구, ${fs.statSync(OUT).size} bytes)`);
