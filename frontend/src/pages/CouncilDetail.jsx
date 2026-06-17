import { useEffect, useState } from "react";
import { getCouncilDetail } from "../api";

const fmt = (n) => (n == null ? "무투표" : Number(n).toLocaleString());

export default function CouncilDetail({ hoecha, code, name }) {
  const [rows, setRows] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    setRows(null); setErr(null);
    if (!hoecha || !code) return;
    getCouncilDetail(hoecha, code).then(setRows).catch((e) => setErr(String(e)));
  }, [hoecha, code]);

  if (!code) return <div className="detail empty">시군구를 클릭하세요.</div>;
  if (err) return <p className="hint">상세를 불러오지 못했습니다. ({err})</p>;
  if (!rows) return <p className="muted">불러오는 중…</p>;
  if (!rows.length) return <p className="hint">이 시군구의 지방의원 데이터가 없습니다.</p>;

  // sgtype + 선거구별 그룹
  const groups = {};
  for (const r of rows) {
    const g = groups[r.sgtype] || (groups[r.sgtype] = {});
    (g[r.sgg] || (g[r.sgg] = [])).push(r);
  }
  const LABEL = { 5: "광역의원 (시·도의원)", 6: "기초의원 (구·시·군의원)" };

  return (
    <>
      <h2>{name} <span className="office-badge">지방의원</span></h2>
      {[5, 6].filter((t) => groups[t]).map((t) => (
        <section key={t}>
          <h3 className="sec-title">{LABEL[t]}</h3>
          {Object.entries(groups[t]).map(([sgg, cands]) => (
            <div key={sgg} className="sgg-block">
              <div className="sgg-name">{sgg}</div>
              <table className="cand-table">
                <tbody>
                  {cands.map((c) => (
                    <tr key={c.idx + c.name} className={c.elected ? "elected-row" : ""}>
                      <td><span className="dot" style={{ background: c.color_hex || "#bbb" }} /></td>
                      <td>{c.name}{c.elected ? <span className="win-tag">당선</span> : null}</td>
                      <td>{c.party}</td>
                      <td className="num">{fmt(c.votes)}</td>
                      <td className="num">{c.rate != null ? c.rate + "%" : ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </section>
      ))}
      <p className="muted">중앙선관위 개표결과. 기초의원은 중선거구제(선거구당 2~4인 선출).</p>
    </>
  );
}
