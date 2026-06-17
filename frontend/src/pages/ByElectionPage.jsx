import { useEffect, useMemo, useState } from "react";
import { getByelectionList, getByelectionDetail } from "../api";

const fmt = (n) => (n == null ? "—" : Number(n).toLocaleString());

export default function ByElectionPage() {
  const [list, setList] = useState([]);
  const [sgId, setSgId] = useState(null);     // 선택된 선거일
  const [sgtype, setSgtype] = useState(null); // 선택된 직종
  const [races, setRaces] = useState(null);
  const [open, setOpen] = useState(null);     // 펼친 선거구 키

  useEffect(() => {
    getByelectionList().then((d) => {
      setList(d);
      if (d.length) setSgId(d[0].sg_id);
    }).catch(() => setList([]));
  }, []);

  const cur = useMemo(() => list.find((d) => d.sg_id === sgId) || null, [list, sgId]);

  // 선거일이 바뀌면 첫 직종 자동 선택
  useEffect(() => {
    if (cur && cur.offices.length) setSgtype(cur.offices[0].sgtype);
  }, [sgId]); // eslint-disable-line react-hooks/exhaustive-deps

  // 직종 상세 로드
  useEffect(() => {
    setRaces(null); setOpen(null);
    if (!sgId || sgtype == null) return;
    getByelectionDetail(sgId, sgtype).then(setRaces).catch(() => setRaces([]));
  }, [sgId, sgtype]);

  const curOffice = cur?.offices.find((o) => o.sgtype === sgtype);

  return (
    <div className="lookup-page bye-page">
      <h2>재·보궐선거</h2>
      <p className="muted">
        전국동시선거(대선·총선·지선) 외에 치러진 재·보궐선거 결과입니다.
        순수 재·보궐선거일과 정규선거일에 함께 치른 동시 보궐을 모두 포함합니다.
        출처: 중앙선거관리위원회 선거통계시스템.
      </p>

      <div className="bye-layout">
        {/* 좌: 선거일 목록 */}
        <aside className="bye-dates">
          {list.map((d) => (
            <button key={d.sg_id}
              className={`bye-date ${d.sg_id === sgId ? "active" : ""}`}
              onClick={() => setSgId(d.sg_id)}>
              <span className={`bye-kind ${d.kind === "재보궐" ? "k-by" : "k-sim"}`}>
                {d.kind === "재보궐" ? "재보궐" : "동시"}
              </span>
              <b>{d.vote_date}</b>
              <span className="bye-label">{d.label}</span>
              <span className="bye-meta">{d.total_races}선거구 · {d.total_seats}석</span>
            </button>
          ))}
        </aside>

        {/* 우: 직종 탭 + 선거구 목록 */}
        <section className="bye-main">
          {!cur ? <p className="muted">불러오는 중…</p> : (
            <>
              <div className="seg bye-offices">
                {cur.offices.map((o) => (
                  <button key={o.sgtype}
                    className={`seg-btn ${o.sgtype === sgtype ? "active" : ""}`}
                    onClick={() => setSgtype(o.sgtype)}>
                    {o.name} <span className="muted">{o.races}</span>
                  </button>
                ))}
              </div>

              {curOffice && (
                <p className="muted bye-sub">
                  {cur.label} · {curOffice.name} — {curOffice.races}개 선거구 / {curOffice.seats}명 당선
                </p>
              )}

              {!races ? <p className="muted">불러오는 중…</p>
                : races.length === 0 ? <p className="hint">데이터가 없습니다.</p> : (
                <ul className="bye-races">
                  {races.map((r) => {
                    const key = r.sido + "|" + r.sgg;
                    const isOpen = open === key;
                    return (
                      <li key={key} className="bye-race">
                        <button className="bye-race-head" onClick={() => setOpen(isOpen ? null : key)}>
                          <span className="bye-region">{r.sido} {r.sgg}</span>
                          <span className="bye-winner">
                            <span className="dot" style={{ background: r.color_hex }} />
                            <b>{r.winner_name}</b>
                            <span className="bye-party" style={{ color: r.color_hex }}>{r.winner_party}</span>
                          </span>
                          <span className="bye-toggle">{isOpen ? "▲" : "▼"}</span>
                        </button>
                        {isOpen && (
                          <table className="prec-table bye-cands">
                            <thead>
                              <tr><th>후보</th><th>정당</th><th className="num">득표수</th><th className="num">득표율</th></tr>
                            </thead>
                            <tbody>
                              {r.candidates.map((c, i) => (
                                <tr key={i} className={c.elected ? "elected-row" : ""}>
                                  <td>{c.elected ? "★ " : ""}{c.name}</td>
                                  <td><span className="dot" style={{ background: c.color_hex }} /> {c.party}</td>
                                  <td className="num">{fmt(c.votes)}</td>
                                  <td className="num">{c.rate == null ? "무투표" : `${c.rate}%`}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
            </>
          )}
        </section>
      </div>
    </div>
  );
}
