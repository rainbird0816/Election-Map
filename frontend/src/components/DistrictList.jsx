import { useState } from "react";

const fmt = (n) => (n == null ? "무투표" : Number(n).toLocaleString());

// 선거구 안 후보 전원(낙선 포함). council/detail·region results 형태 모두 수용.
function Cands({ rows }) {
  return (
    <table className="cand-table">
      <tbody>
        {rows.map((c, i) => {
          const won = c.elected || c.is_elected;
          return (
            <tr key={i} className={won ? "elected-row" : ""}>
              <td><span className="dot" style={{ background: c.color_hex || "#bbb" }} /></td>
              <td>{c.name || c.cand}{won ? <span className="win-tag">당선</span> : null}</td>
              <td>{c.party || c.party_name}</td>
              <td className="num">{fmt(c.votes)}</td>
              <td className="num">{(c.rate ?? c.vote_rate) != null ? `${c.rate ?? c.vote_rate}%` : ""}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

// 선거구별 목록: 기본은 '선거구명 + 당선자' 한 줄, 클릭하면 후보 전원(낙선 포함)을 펼침.
// groups = { 선거구명: [후보…] }
export default function DistrictList({ groups, empty = "데이터 없음" }) {
  const entries = Object.entries(groups || {});
  const [open, setOpen] = useState({});
  if (!entries.length) return <p className="muted">{empty}</p>;
  return (
    <div className="dist-list">
      {entries.map(([sgg, cands]) => {
        const win = cands.find((c) => c.elected || c.is_elected) || cands[0];
        const isOpen = !!open[sgg];
        return (
          <div key={sgg} className="dist-item">
            <button type="button" className={"dist-row" + (isOpen ? " open" : "")}
              onClick={() => setOpen((o) => ({ ...o, [sgg]: !o[sgg] }))}>
              <span className="dist-exp">{isOpen ? "▾" : "▸"}</span>
              <span className="dist-sgg">{sgg}</span>
              <span className="dot" style={{ background: win?.color_hex || "#bbb" }} />
              <span className="dist-win">{win?.name || win?.cand}</span>
              <span className="dist-party">{win?.party || win?.party_name}</span>
            </button>
            {isOpen && <Cands rows={cands} />}
          </div>
        );
      })}
    </div>
  );
}
