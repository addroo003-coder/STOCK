"use client";

import { useMemo, useState } from "react";
import { scenarioText, sectors, type Scenario } from "./data";
import { earningsByStock } from "./earnings-data";
import { marketSourcesByStock } from "./market-sources";

const beta: Record<string, number> = { semi: 2, power: 1, robot: 4, nuclear: 1, space: 3, bio: 4, battery: 3 };

function scoreFor(key: string, base: number, delta: number, riskBudget: number) {
  return Math.max(0, Math.min(99, Math.round(base + delta + (riskBudget - 3) * (beta[key] ?? 2))));
}

function scoreLabel(score: number) {
  if (score >= 88) return "최우선";
  if (score >= 80) return "비중확대";
  if (score >= 72) return "선별접근";
  return "확인구간";
}

function formatFigure(value: number | null) {
  return value == null ? "—" : value.toLocaleString("ko-KR");
}

function formatChange(value: number | null) {
  if (value == null) return "—";
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}%`;
}

function changeTone(value: number | null) {
  if (value == null || value === 0) return "flat";
  return value > 0 ? "up" : "down";
}

function formatNewsDate(value?: string) {
  if (!value || value.length !== 8) return value ?? "";
  return `${value.slice(0, 4)}.${value.slice(4, 6)}.${value.slice(6, 8)}`;
}

function earningsEvidence(name: string, earnings: typeof earningsByStock[string] | undefined) {
  if (!earnings) return `${name}의 분기 실적은 공시 원문 확인 후 반영합니다.`;
  if (earnings.q2.status !== "확정") {
    return `1Q26 매출 ${formatFigure(earnings.q1.revenue)}억원·영업이익 ${formatFigure(earnings.q1.operatingProfit)}억원을 기록했습니다. 2Q26은 예측치를 섞지 않고 확정 집계 확인 후 반영합니다.`;
  }
  return `2Q26 매출 ${formatFigure(earnings.q2.revenue)}억원·영업이익 ${formatFigure(earnings.q2.operatingProfit)}억원입니다. 매출은 YoY ${formatChange(earnings.comparisons.q2RevenueYoy)}, 영업이익은 YoY ${formatChange(earnings.comparisons.q2OperatingProfitYoy)}로 현재 실적 판정은 ‘${earnings.interpretation}’입니다.`;
}

export default function InvestmentAtlas() {
  const [scenario, setScenario] = useState<Scenario>("base");
  const [riskBudget, setRiskBudget] = useState(3);
  const [sectorKey, setSectorKey] = useState("semi");
  const [selectedRef, setSelectedRef] = useState({ sectorKey: "semi", segmentIndex: 0, stockIndex: 0 });
  const [query, setQuery] = useState("");
  const [copied, setCopied] = useState(false);

  const scoredSectors = useMemo(() => sectors
    .map((sector) => ({ ...sector, currentScore: scoreFor(sector.key, sector.score, sector.delta[scenario], riskBudget) }))
    .sort((a, b) => b.currentScore - a.currentScore), [scenario, riskBudget]);

  const activeSector = sectors.find((sector) => sector.key === sectorKey) ?? sectors[0];
  const selectedSector = sectors.find((sector) => sector.key === selectedRef.sectorKey) ?? sectors[0];
  const selectedSegment = selectedSector.segments[selectedRef.segmentIndex] ?? selectedSector.segments[0];
  const selectedStock = selectedSegment.stocks[selectedRef.stockIndex] ?? selectedSegment.stocks[0];
  const selectedEarnings = earningsByStock[selectedStock.name];
  const selectedSources = marketSourcesByStock[selectedStock.name];
  const selectedScore = scoreFor(selectedSector.key, selectedSector.score, selectedSector.delta[scenario], riskBudget);

  const allStocks = useMemo(() => sectors.flatMap((sector) => sector.segments.flatMap((segment, segmentIndex) =>
    segment.stocks.map((stock, stockIndex) => ({ sector, segment, segmentIndex, stock, stockIndex }))
  )), []);
  const uniqueStockCount = useMemo(() => new Set(allStocks.map((item) => item.stock.name)).size, [allStocks]);
  const segmentCount = useMemo(() => sectors.reduce((sum, sector) => sum + sector.segments.length, 0), []);

  const results = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    if (!keyword) return [];
    return allStocks.filter(({ stock, sector, segment }) =>
      `${stock.name} ${stock.role} ${sector.name} ${segment.name}`.toLowerCase().includes(keyword)
    ).slice(0, 12);
  }, [allStocks, query]);

  function chooseSector(key: string) {
    const next = sectors.find((sector) => sector.key === key) ?? sectors[0];
    setSectorKey(next.key);
    setSelectedRef({ sectorKey: next.key, segmentIndex: 0, stockIndex: 0 });
  }

  function chooseStock(nextSectorKey: string, segmentIndex: number, stockIndex: number, scroll = false) {
    setSectorKey(nextSectorKey);
    setSelectedRef({ sectorKey: nextSectorKey, segmentIndex, stockIndex });
    setQuery("");
    if (scroll) window.setTimeout(() => document.getElementById("stock-detail")?.scrollIntoView({ behavior: "smooth", block: "start" }), 60);
  }

  const memo = `[성장산업 투자지도]\n시장 시나리오: ${scenarioText[scenario].label} / 위험예산: ${riskBudget}단계\n섹터: ${selectedSector.name} (${selectedScore}점·${scoreLabel(selectedScore)})\n세부 산업: ${selectedSegment.name}\n핵심 종목: ${selectedStock.name} [${selectedStock.style}]\n밸류체인 역할: ${selectedStock.role}\n핵심 투자모멘텀: ${selectedStock.note}\n왜 지금인가: ${selectedSegment.catalyst}\n실적 근거: ${earningsEvidence(selectedStock.name, selectedEarnings)}\n모멘텀 훼손 조건: ${selectedSegment.risk}\n다음 확인 지표: ${selectedSegment.check}\n최근 리포트: ${selectedSources?.report ? `${selectedSources.report.broker} · ${selectedSources.report.title} (${selectedSources.report.date})` : "공개 리포트 없음"}\n최근 관련 뉴스: ${selectedSources?.news ? `${selectedSources.news.title} (${formatNewsDate(selectedSources.news.date)})` : "관련 뉴스 확인 중"}\n2026년 1Q 실적(억원): 매출 ${formatFigure(selectedEarnings?.q1.revenue ?? null)} / 영업이익 ${formatFigure(selectedEarnings?.q1.operatingProfit ?? null)}\n2026년 2Q 실적(억원): 매출 ${formatFigure(selectedEarnings?.q2.revenue ?? null)} / 영업이익 ${formatFigure(selectedEarnings?.q2.operatingProfit ?? null)} / ${selectedEarnings?.interpretation ?? "검증 대기"}\n시나리오 대응: ${selectedSector.actions[scenario]}\n※ 산업 분류와 상대평가를 위한 정리이며 개별 종목 매매 신호가 아닙니다.`;

  async function copyMemo() {
    await navigator.clipboard.writeText(memo);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1800);
  }

  return (
    <main>
      <section className="hero" aria-labelledby="page-title">
        <nav className="topbar">
          <a className="brand" href="#top" id="top"><span>A</span> GROWTH ATLAS</a>
          <div className="asof"><i /> 2026.08 · 국내 성장산업 지도</div>
        </nav>

        <div className="hero-grid">
          <div className="hero-copy">
            <p className="eyebrow">KOREA GROWTH INDUSTRY MAP</p>
            <h1 id="page-title">산업을 이해하고,<br /><em>종목의 자리를 찾는다.</em></h1>
            <p>반도체부터 전력·로봇·원전·우주항공·바이오·배터리까지, 국내 핵심 성장산업을 같은 구조로 정리한 투자 아틀라스입니다.</p>
          </div>
          <div className="atlas-counts" aria-label="투자지도 구성">
            <div><strong>0{sectors.length}</strong><span>핵심 섹터</span></div>
            <div><strong>{segmentCount}</strong><span>세부 산업</span></div>
            <div><strong>{uniqueStockCount}</strong><span>핵심 종목</span></div>
          </div>
        </div>

        <div className="regime-panel">
          <div className="regime-summary">
            <span>MARKET REGIME</span>
            <strong>{scenarioText[scenario].kicker}</strong>
            <p>{scenarioText[scenario].summary}</p>
          </div>
          <fieldset>
            <legend>시장 시나리오</legend>
            <div className="segmented">
              {(["bull", "base", "bear"] as Scenario[]).map((item) => (
                <button key={item} className={scenario === item ? "active" : ""} onClick={() => setScenario(item)}>{scenarioText[item].label}</button>
              ))}
            </div>
          </fieldset>
          <fieldset className="risk-control">
            <legend>위험예산 <b>{riskBudget}/5</b></legend>
            <input aria-label="위험예산" type="range" min="1" max="5" value={riskBudget} onChange={(event) => setRiskBudget(Number(event.target.value))} />
            <div><span>보수</span><span>공격</span></div>
          </fieldset>
          <div className="top-pick"><span>현재 우선 섹터</span><strong>{scoredSectors[0].name}</strong><em>{scoredSectors[0].currentScore}점</em></div>
        </div>

        <div className="score-ribbon">
          {scoredSectors.map((sector, index) => (
            <button key={sector.key} onClick={() => { chooseSector(sector.key); document.getElementById("atlas")?.scrollIntoView({ behavior: "smooth" }); }}>
              <span>0{index + 1}</span><strong>{sector.name}</strong><em>{sector.currentScore}</em>
            </button>
          ))}
        </div>
      </section>

      <section className="atlas" id="atlas" aria-labelledby="atlas-title">
        <div className="section-heading">
          <div><p className="eyebrow">SECTOR → VALUE CHAIN → STOCK</p><h2 id="atlas-title">성장산업 핵심지도</h2></div>
          <div className="search-wrap">
            <label htmlFor="stock-search">종목·산업 검색</label>
            <div className="search-box"><span>⌕</span><input id="stock-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="예: 한미반도체, 전공정, ESS" /></div>
            {query && <div className="search-results">
              <div className="result-head"><span>검색 결과</span><b>{results.length}</b></div>
              {results.length ? results.map(({ sector, segment, segmentIndex, stock, stockIndex }) => (
                <button key={`${sector.key}-${segmentIndex}-${stockIndex}`} onClick={() => chooseStock(sector.key, segmentIndex, stockIndex, true)}>
                  <span style={{ background: sector.accent }} />
                  <strong>{stock.name}</strong>
                  <em>{sector.name} · {segment.name}</em>
                </button>
              )) : <p>일치하는 종목이나 산업이 없습니다.</p>}
            </div>}
          </div>
        </div>

        <div className="sector-tabs" role="tablist" aria-label="산업 선택">
          {sectors.map((sector) => (
            <button role="tab" aria-selected={sectorKey === sector.key} key={sector.key} className={sectorKey === sector.key ? "active" : ""} onClick={() => chooseSector(sector.key)} style={{ "--accent": sector.accent } as React.CSSProperties}>
              <span>{sector.short}</span><strong>{sector.name}</strong>
            </button>
          ))}
        </div>

        <div className="sector-intro" style={{ "--accent": activeSector.accent } as React.CSSProperties}>
          <div className="sector-number">{String(sectors.findIndex((sector) => sector.key === activeSector.key) + 1).padStart(2, "0")}</div>
          <div><p>{activeSector.regime}</p><h3>{activeSector.name}</h3><span>{activeSector.overview}</span></div>
          <aside><small>CORE QUESTION</small><strong>{activeSector.coreQuestion}</strong></aside>
        </div>

        <div className="segment-grid">
          {activeSector.segments.map((segment, segmentIndex) => (
            <article className="segment-card" key={segment.name} style={{ "--accent": activeSector.accent } as React.CSSProperties}>
              <header><span>{String(segmentIndex + 1).padStart(2, "0")}</span><div><p>SUB-INDUSTRY</p><h3>{segment.name}</h3></div></header>
              <p className="segment-definition">{segment.definition}</p>
              <div className="stock-list">
                {segment.stocks.map((stock, stockIndex) => {
                  const isSelected = selectedRef.sectorKey === activeSector.key && selectedRef.segmentIndex === segmentIndex && selectedRef.stockIndex === stockIndex;
                  return <button key={`${stock.name}-${stockIndex}`} className={isSelected ? "selected" : ""} onClick={() => chooseStock(activeSector.key, segmentIndex, stockIndex, true)}>
                    <div><strong>{stock.name}</strong><span className={`style style-${stock.style}`}>{stock.style}</span><span className={`earnings-mini ${earningsByStock[stock.name]?.q2.status === "확정" ? "confirmed" : "pending"}`}>{earningsByStock[stock.name]?.q2.status === "확정" ? "2Q 확정" : "2Q 확인 중"}</span></div>
                    <p>{stock.role}</p><i>→</i>
                  </button>;
                })}
              </div>
              <footer><span>WATCH</span><p>{segment.check}</p></footer>
            </article>
          ))}
        </div>
      </section>

      <section className="stock-detail" id="stock-detail" aria-labelledby="detail-title" style={{ "--accent": selectedSector.accent } as React.CSSProperties}>
        <div className="detail-heading">
          <div><p className="eyebrow">STOCK POSITIONING · {selectedSector.short}</p><h2 id="detail-title">{selectedStock.name}</h2><span>{selectedSector.name} / {selectedSegment.name}</span></div>
          <button className="copy-button" onClick={copyMemo}><span>{copied ? "✓" : "↗"}</span>{copied ? "복사 완료" : "분석 메모 복사"}</button>
        </div>

        <div className="detail-grid">
          <article className="position-card">
            <div className="position-top"><span className={`style style-${selectedStock.style}`}>{selectedStock.style}</span><em>{scoreLabel(selectedScore)}</em></div>
            <strong className="detail-score">{selectedScore}<small>/100</small></strong>
            <p className="role">{selectedStock.role}</p>
            <p className="stock-note">{selectedStock.note}</p>
          </article>

          <article className="logic-card">
            <div><span className="logic-icon positive">+</span><section><small>상승 촉매</small><p>{selectedSegment.catalyst}</p></section></div>
            <div><span className="logic-icon negative">!</span><section><small>핵심 리스크</small><p>{selectedSegment.risk}</p></section></div>
            <div><span className="logic-icon watch">●</span><section><small>반드시 확인할 지표</small><p>{selectedSegment.check}</p></section></div>
          </article>

          <article className="scenario-card">
            <span>SCENARIO PLAYBOOK</span>
            <h3>{scenarioText[scenario].label} 시나리오 대응</h3>
            <p>{selectedSector.actions[scenario]}</p>
            <div className="scenario-scale">
              {(["bear", "base", "bull"] as Scenario[]).map((item) => <button key={item} onClick={() => setScenario(item)} className={scenario === item ? "active" : ""}><i />{scenarioText[item].label}</button>)}
            </div>
          </article>
        </div>

        <section className="momentum-panel" aria-labelledby="momentum-title">
          <header className="momentum-heading">
            <div><p className="eyebrow">STOCK MOMENTUM BRIEF</p><h3 id="momentum-title">핵심 투자모멘텀</h3><span>실적·산업 촉매·공개 리포트·최근 뉴스를 교차해 보는 종목별 체크리스트</span></div>
            <div><span>업데이트</span><strong>{selectedSources?.updatedAt ?? "2026-08-27"}</strong></div>
          </header>

          <div className="momentum-content">
            <article className="momentum-thesis">
              <span className="momentum-index">01 · CORE THESIS</span>
              <h4>{selectedStock.note}</h4>
              <div><small>왜 지금인가</small><p>{selectedSegment.catalyst}</p></div>
            </article>

            <article className="momentum-checks">
              <div><span className="momentum-icon evidence">E</span><section><small>실적과 연결되는 근거</small><p>{earningsEvidence(selectedStock.name, selectedEarnings)}</p></section></div>
              <div><span className="momentum-icon trigger">T</span><section><small>다음 촉매·확인지표</small><p>{selectedSegment.check}</p></section></div>
              <div><span className="momentum-icon invalidate">R</span><section><small>모멘텀 훼손 조건</small><p>{selectedSegment.risk}</p></section></div>
            </article>

            <aside className="source-stack">
              <article>
                <header><span>BROKER REPORT</span>{selectedSources?.report && <em>{selectedSources.report.date}</em>}</header>
                {selectedSources?.report ? <><h4>{selectedSources.report.title}</h4><p>{selectedSources.report.broker}</p><div><a href={selectedSources.report.url} target="_blank" rel="noreferrer">리포트 요약 ↗</a><a href={selectedSources.report.pdfUrl} target="_blank" rel="noreferrer">PDF 원문 ↗</a></div></> : <><h4>공개 리포트 없음</h4><p>기업 IR·공시와 최근 뉴스 중심으로 확인합니다.</p><a href={selectedSources?.reportListUrl} target="_blank" rel="noreferrer">리포트 검색 ↗</a></>}
              </article>
              <article>
                <header><span>LATEST RELEVANT NEWS</span>{selectedSources?.news && <em>{formatNewsDate(selectedSources.news.date)}</em>}</header>
                {selectedSources?.news ? <><h4>{selectedSources.news.title}</h4><p>{selectedSources.news.office}</p><a href={selectedSources.news.url} target="_blank" rel="noreferrer">뉴스 원문 ↗</a></> : <><h4>관련 뉴스 확인 중</h4><a href={selectedSources?.newsListUrl} target="_blank" rel="noreferrer">뉴스 목록 ↗</a></>}
              </article>
            </aside>
          </div>

          <footer className="momentum-source-note"><i /> 리포트 제목·뉴스는 공개 원문으로 연결하며, 투자모멘텀 해석은 산업 구조와 확정 실적을 함께 반영합니다.</footer>
        </section>

        {selectedEarnings && <section className="earnings-panel" aria-labelledby="earnings-title">
          <header className="earnings-heading">
            <div>
              <p className="eyebrow">2026 QUARTERLY EARNINGS</p>
              <h3 id="earnings-title">1분기 → 2분기 실적 추세</h3>
              <span>분기 단독 · {selectedEarnings.basis} 기준 · 단위 억원</span>
            </div>
            <div className="earnings-status">
              <strong>{selectedEarnings.interpretation}</strong>
              <span className={selectedEarnings.q2.status === "확정" ? "confirmed" : "pending"}>{selectedEarnings.q2.status === "확정" ? "2Q 확정치" : "2Q 공시 집계 확인 중"}</span>
            </div>
          </header>

          <div className="earnings-content">
            {[{ label: "1Q26", quarter: selectedEarnings.q1 }, { label: "2Q26", quarter: selectedEarnings.q2 }].map(({ label, quarter }) => (
              <article className="quarter-card" key={label}>
                <div className="quarter-title"><strong>{label}</strong><span className={quarter.status === "확정" ? "confirmed" : "pending"}>{quarter.status === "확정" ? "확정" : "확인 중"}</span></div>
                {quarter.status === "확정" ? <div className="metric-grid">
                  <div><span>매출액</span><strong>{formatFigure(quarter.revenue)}</strong><small>억원</small></div>
                  <div><span>영업이익</span><strong>{formatFigure(quarter.operatingProfit)}</strong><small>억원</small></div>
                  <div><span>당기순이익</span><strong>{formatFigure(quarter.netIncome)}</strong><small>억원</small></div>
                  <div><span>영업이익률</span><strong>{quarter.operatingMargin == null ? "—" : quarter.operatingMargin.toFixed(1)}</strong><small>%</small></div>
                </div> : <div className="pending-copy"><strong>예측치는 표시하지 않습니다.</strong><p>공시 기반 확정 집계가 확인되는 즉시 숫자를 반영합니다.</p></div>}
              </article>
            ))}

            <article className="change-card">
              <div className="change-title"><span>2Q26 CHANGE</span><strong>성장률 비교</strong></div>
              <div className="change-list">
                <div><span>매출액 YoY</span><strong className={changeTone(selectedEarnings.comparisons.q2RevenueYoy)}>{formatChange(selectedEarnings.comparisons.q2RevenueYoy)}</strong></div>
                <div><span>매출액 QoQ</span><strong className={changeTone(selectedEarnings.comparisons.q2RevenueQoq)}>{formatChange(selectedEarnings.comparisons.q2RevenueQoq)}</strong></div>
                <div><span>영업이익 YoY</span><strong className={changeTone(selectedEarnings.comparisons.q2OperatingProfitYoy)}>{formatChange(selectedEarnings.comparisons.q2OperatingProfitYoy)}</strong></div>
                <div><span>영업이익 QoQ</span><strong className={changeTone(selectedEarnings.comparisons.q2OperatingProfitQoq)}>{formatChange(selectedEarnings.comparisons.q2OperatingProfitQoq)}</strong></div>
              </div>
            </article>
          </div>

          <footer className="earnings-source">
            <p><i /> 최종 검증 {selectedEarnings.verifiedAt} · {selectedEarnings.sourceLabel}</p>
            <div><a href={selectedEarnings.sourceUrl} target="_blank" rel="noreferrer">재무정보 원문 ↗</a><a href="https://dart.fss.or.kr/" target="_blank" rel="noreferrer">DART 공시 ↗</a></div>
          </footer>
        </section>}

        <footer className="site-footer">
          <div><p>산업 방향 참고자료</p><section>{selectedSector.sources.map((source) => <a key={source.href} href={source.href} target="_blank" rel="noreferrer">{source.label} ↗</a>)}</section></div>
          <small>표시 점수는 성장성·실적가시성·정책·모멘텀과 선택한 시장 시나리오를 결합한 상대평가입니다. 수익률 전망치나 개별 종목의 매수·매도 신호가 아닙니다.</small>
        </footer>
      </section>
    </main>
  );
}
