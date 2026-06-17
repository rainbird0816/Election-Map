import { useEffect, useState } from "react";
import { getRegionTimeline } from "../api";

const fmt = (n) => (n == null ? "—" : Number(n).toLocaleString());
function textOn(hex) {
  if (!hex || hex[0] !== "#" || hex.length < 7) return "#111";
  const r = parseInt(hex.slice(1, 3), 16), g = parseInt(hex.slice(3, 5), 16), b = parseInt(hex.slice(5, 7), 16);
  return (0.299 * r + 0.587 * g + 0.114 * b) > 150 ? "#111" : "#fff";
}

function CandTable({ candidates }) {
  return (
    <table className="prec-table tl-cands">
      <thead><tr><th>후보</th><th>정당</th><th className="num">득표</th><th className="num">%</th></tr></thead>
      <tbody>
        {candidates.map((c, i) => (
          <tr key={i} className={c.elected ? "elected-row" : ""}>
            <td>{c.elected ? "★ " : ""}{c.name}</td>
            <td><span className="dot" style={{ background: c.color }} /> {c.party}</td>
            <td className="num">{fmt(c.votes)}</td>
            <td className="num">{c.rate == null ? "무투표" : `${c.rate}%`}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function RegionTimeline({ code, name }) {
  const [data, setData] = useState(null);
  const [open, setOpen] = useState(null); // `${office}|${year}`

  useEffect(() => { setData(null); setOpen(null); if (code) getRegionTimeline(code).then(setData).catch(() => setData(null)); }, [code]);

  if (!code) return null;
  if (!data) return <div className="detail"><p className="muted">불러오는 중…</p></div>;

  return (
    <div className="region-timeline">
      <h2>{name} <span className="office-badge">연도별 선출직</span></h2>
      <p className="muted">{data.region.sido_name} {data.region.name} 유권자가 뽑는 모든 선출직의 역대 결과. 정규 선거 사이의 <em className="tl-byebadge inline">보궐</em> 칸은 재·보궐선거로 당선인이 바뀐 연도입니다. 칸을 클릭하면 후보별 득표가 펼쳐집니다.</p>

      {data.sections.map((s) => (
        <div key={s.office} className="tl-section">
          <h3 className="tl-office">{s.office}</h3>
          <div className="tl-years">
            {s.years.map((y) => {
              const key = s.office + "|" + y.year + "|" + (y.byelection ? y.date : "r");
              const isOpen = open === key;
              // 대표(1위/당선/다수당) 표시
              let head, color = "#e5e7eb";
              if (s.kind === "single") {
                const w = y.candidates[0];
                head = w ? w.name : "—"; color = w?.color || color;
              } else if (s.kind === "races") {
                const ws = y.races.map((r) => (r.candidates.find((c) => c.elected) || r.candidates[0]));
                head = ws.map((w) => w?.name).filter(Boolean).join(" · ") || "—";
                color = ws[0]?.color || color;
              } else if (s.kind === "council") {
                const top = y.seats[0];
                head = top ? `${top.party} ${top.seats}석` : "—"; color = top?.color || color;
              } else if (s.kind === "edu") {
                head = y.name ? `${y.name}` : "—"; color = y.color || color;
              }
              const expandable = s.kind !== "edu";
              return (
                <div key={key} className="tl-cell-wrap">
                  <button className={`tl-cell ${isOpen ? "open" : ""} ${y.byelection ? "tl-bye" : ""}`} disabled={!expandable}
                    style={{ background: color, color: textOn(color) }}
                    onClick={() => expandable && setOpen(isOpen ? null : key)}>
                    <span className="tl-year">{y.year || y.label}{y.byelection && <em className="tl-byebadge">보궐</em>}</span>
                    <span className="tl-head">{head}</span>
                    {s.kind === "edu" && y.lean && <span className="tl-sub">{y.lean}</span>}
                  </button>
                  {isOpen && (
                    <div className="tl-detail">
                      {s.kind === "single" && <CandTable candidates={y.candidates} />}
                      {(s.kind === "races" || s.kind === "council") && (
                        <>
                          {s.kind === "council" && (
                            <div className="tl-seats">
                              {y.seats.map((p) => (
                                <span key={p.party} className="tl-seat" style={{ borderColor: p.color }}>
                                  <span className="dot" style={{ background: p.color }} /> {p.party} <b>{p.seats}</b>
                                </span>
                              ))}
                            </div>
                          )}
                          {y.races.map((r) => (
                            <div key={r.sgg} className="tl-race">
                              <div className="tl-race-name">{r.sgg}</div>
                              <CandTable candidates={r.candidates} />
                            </div>
                          ))}
                        </>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
