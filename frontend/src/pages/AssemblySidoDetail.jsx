import { useEffect, useState } from "react";
import { getAssemblySido } from "../api";

const fmt = (n) => (n == null ? "무투표" : Number(n).toLocaleString());

// 총선 시도 드릴다운: 해당 시도의 선거구 목록(자연순) → 선거구 클릭 시 후보 전원
export default function AssemblySidoDetail({ daesu, sido, sidoName }) {
  const [rows, setRows] = useState(null);
  const [open, setOpen] = useState(null);

  useEffect(() => {
    setRows(null); setOpen(null);
    if (!daesu || !sido) return;
    getAssemblySido(daesu, sido).then(setRows).catch(() => setRows([]));
  }, [daesu, sido]);

  if (!rows) return <aside className="detail"><p className="muted">불러오는 중…</p></aside>;
  if (!rows.length) {
    return <aside className="detail"><h2>{sidoName}</h2>
      <p className="hint">이 대수의 선거구별 데이터가 없습니다(13대는 시도 집계만).</p></aside>;
  }

  return (
    <aside className="detail">
      <h2>{sidoName} <span className="office-badge">{daesu}대 지역구 {rows.length}석</span></h2>
      <p className="muted">선거구를 클릭하면 후보 전원(낙선 포함)이 펼쳐집니다.</p>
      <ul className="sgg-list">
        {rows.map((r) => (
          <li key={r.sgg}>
            <button className="sgg-row" onClick={() => setOpen(open === r.sgg ? null : r.sgg)}>
              <span className="sgg-tri">{open === r.sgg ? "▾" : "▸"}</span>
              <span className="sgg-nm">{r.sgg}</span>
              <span className="dot" style={{ background: r.color_hex }} />
              <span className="sgg-win">{r.winner_name}</span>
              <span className="sgg-party">{r.winner_party}</span>
            </button>
            {open === r.sgg && (
              <table className="cand-table">
                <tbody>
                  {r.candidates.map((c, i) => (
                    <tr key={i} className={c.elected ? "elected-row" : ""}>
                      <td><span className="dot" style={{ background: c.color_hex || "#bbb" }} /></td>
                      <td>{c.name}{c.elected ? <span className="win-tag">당선</span> : null}</td>
                      <td>{c.party}</td>
                      <td className="num">{fmt(c.votes)}</td>
                      <td className="num">{c.rate != null ? `${c.rate}%` : ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </li>
        ))}
      </ul>
    </aside>
  );
}
