import { readFile, writeFile } from "node:fs/promises";

const MARKET_ENDPOINT = "https://m.stock.naver.com/api/stocks/marketValue";
const FINANCE_ENDPOINT = "https://m.stock.naver.com/api/stock";
const CODE_OVERRIDES = {
  "LIG넥스원": "079550",
  "씨아이에스": "222080",
  "씨메스": "475400",
};

// ── 항상 "최신 확정 분기(q2) + 그 직전 분기(q1)"를 오늘 날짜 기준으로 자동으로 계산한다.
// 분기말(3/6/9/12월)이 지나면 다음 실행부터 자동으로 그 분기를 추적 대상으로 잡고,
// 아직 공시가 안 나온 상태면(actualPeriods에 없으면) quarter()가 status: "미발표"로
// 표시하므로 화면에는 "확인 중"으로만 뜨고 숫자는 확정 후에 자연스럽게 채워진다.
// -> 이 파일은 그래서 이후로 사람이 분기를 손으로 바꿔줄 필요가 없다.
const QUARTER_MONTHS = ["03", "06", "09", "12"];

function periodKey(year, monthStr) {
  return `${year}${monthStr}`;
}

function prevQuarterPeriod(period) {
  const year = Number(period.slice(0, 4));
  const idx = QUARTER_MONTHS.indexOf(period.slice(4));
  return idx === 0 ? periodKey(year - 1, "12") : periodKey(year, QUARTER_MONTHS[idx - 1]);
}

function sameQuarterLastYear(period) {
  return periodKey(Number(period.slice(0, 4)) - 1, period.slice(4));
}

function latestQuarterEndPeriod(today = new Date()) {
  const y = today.getUTCFullYear();
  const m = today.getUTCMonth() + 1; // 1-12
  if (m >= 10) return periodKey(y, "09"); // 10~12월 -> 3분기(9월말) 방금 끝남
  if (m >= 7) return periodKey(y, "06");  // 7~9월   -> 2분기(6월말) 방금 끝남
  if (m >= 4) return periodKey(y, "03");  // 4~6월   -> 1분기(3월말) 방금 끝남
  return periodKey(y - 1, "12");          // 1~3월   -> 작년 4분기(12월말) 방금 끝남
}

const Q2 = latestQuarterEndPeriod();
const Q1 = prevQuarterPeriod(Q2);
const Q2_PRIOR_YEAR = sameQuarterLastYear(Q2);
const Q1_PRIOR_QUARTER = prevQuarterPeriod(Q1);
const PERIODS = [...new Set([Q1_PRIOR_QUARTER, Q2_PRIOR_YEAR, Q1, Q2])];
const VERIFIED_AT = new Date().toISOString().slice(0, 10);

async function fetchJson(url, attempts = 3) {
  let lastError;
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      const response = await fetch(url, {
        headers: {
          accept: "application/json",
          "user-agent": "Mozilla/5.0 (compatible; GrowthAtlas/1.0)",
        },
      });
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
      return await response.json();
    } catch (error) {
      lastError = error;
      await new Promise((resolve) => setTimeout(resolve, 450 * attempt));
    }
  }
  throw lastError;
}

async function parallelMap(items, limit, mapper) {
  const results = new Array(items.length);
  let cursor = 0;
  async function worker() {
    while (cursor < items.length) {
      const index = cursor;
      cursor += 1;
      results[index] = await mapper(items[index], index);
    }
  }
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, worker));
  return results;
}

async function getMarketStocks(market) {
  const first = await fetchJson(`${MARKET_ENDPOINT}/${market}?page=1&pageSize=100`);
  const pageCount = Math.ceil(first.totalCount / 100);
  const pages = Array.from({ length: pageCount - 1 }, (_, index) => index + 2);
  const rest = await parallelMap(pages, 8, (page) =>
    fetchJson(`${MARKET_ENDPOINT}/${market}?page=${page}&pageSize=100`),
  );
  return [first, ...rest].flatMap((page) => page.stocks ?? []);
}

function parseValue(value) {
  if (value == null || value === "-" || value === "") return null;
  const number = Number(String(value).replaceAll(",", ""));
  return Number.isFinite(number) ? number : null;
}

function percentChange(current, previous) {
  if (current == null || previous == null || previous === 0) return null;
  return Number((((current - previous) / Math.abs(previous)) * 100).toFixed(1));
}

function getRow(rows, title) {
  return rows.find((row) => row.title === title)?.columns ?? {};
}

function valueAt(columns, period) {
  return parseValue(columns[period]?.value);
}

function quarter(period, actualPeriods, revenue, operatingProfit, netIncome, operatingMargin) {
  const status = actualPeriods.has(period) ? "확정" : "미발표";
  return {
    period,
    status,
    revenue: status === "확정" ? valueAt(revenue, period) : null,
    operatingProfit: status === "확정" ? valueAt(operatingProfit, period) : null,
    netIncome: status === "확정" ? valueAt(netIncome, period) : null,
    operatingMargin: status === "확정" ? valueAt(operatingMargin, period) : null,
  };
}

function classify(record, previous) {
  const q2 = record.q2;
  const priorYear = previous[Q2_PRIOR_YEAR];
  if (q2.status !== "확정" || q2.operatingProfit == null) return "검증 대기";
  if (q2.operatingProfit > 0 && record.q1.operatingProfit != null && record.q1.operatingProfit <= 0) return "흑자전환";
  if (q2.operatingProfit < 0) return "손실 구간";
  const yoy = percentChange(q2.operatingProfit, priorYear.operatingProfit);
  const qoq = percentChange(q2.operatingProfit, record.q1.operatingProfit);
  if ((yoy ?? 0) > 10 && (qoq ?? 0) > 10) return "이익 가속";
  if ((yoy ?? 0) > 0 && (qoq ?? 0) >= 0) return "이익 개선";
  if ((yoy ?? 0) > 0 && (qoq ?? 0) < 0) return "전년비 성장·분기 둔화";
  if ((yoy ?? 0) < 0 && (qoq ?? 0) > 0) return "분기 회복";
  if ((yoy ?? 0) < 0 && (qoq ?? 0) < 0) return "실적 둔화";
  return "혼조";
}

function toRecord(company, code, payload) {
  const info = payload.financeInfo ?? { trTitleList: [], rowList: [] };
  const actualPeriods = new Set(
    info.trTitleList.filter((period) => period.isConsensus === "N").map((period) => period.key),
  );
  const revenue = getRow(info.rowList, "매출액");
  const operatingProfit = getRow(info.rowList, "영업이익");
  const netIncome = getRow(info.rowList, "당기순이익");
  const operatingMargin = getRow(info.rowList, "영업이익률");
  const q1 = quarter(Q1, actualPeriods, revenue, operatingProfit, netIncome, operatingMargin);
  const q2 = quarter(Q2, actualPeriods, revenue, operatingProfit, netIncome, operatingMargin);
  const previous = Object.fromEntries(PERIODS.map((period) => [period, {
    revenue: valueAt(revenue, period),
    operatingProfit: valueAt(operatingProfit, period),
    netIncome: valueAt(netIncome, period),
    operatingMargin: valueAt(operatingMargin, period),
  }]));
  const consolidated = info.rowList.some((row) => row.title === "지배주주순이익");
  const record = {
    company,
    code,
    basis: consolidated ? "연결" : "별도·개별",
    unit: "억원",
    q1,
    q2,
    comparisons: {
      q1RevenueQoq: percentChange(q1.revenue, previous[Q1_PRIOR_QUARTER].revenue),
      q1OperatingProfitQoq: percentChange(q1.operatingProfit, previous[Q1_PRIOR_QUARTER].operatingProfit),
      q2RevenueYoy: percentChange(q2.revenue, previous[Q2_PRIOR_YEAR].revenue),
      q2RevenueQoq: percentChange(q2.revenue, q1.revenue),
      q2OperatingProfitYoy: percentChange(q2.operatingProfit, previous[Q2_PRIOR_YEAR].operatingProfit),
      q2OperatingProfitQoq: percentChange(q2.operatingProfit, q1.operatingProfit),
    },
    interpretation: "",
    verifiedAt: VERIFIED_AT,
    sourceLabel: "공시 기반 집계 · 네이버증권/FnGuide",
    sourceUrl: `https://finance.naver.com/item/main.naver?code=${code}`,
    dartUrl: `https://dart.fss.or.kr/dsab002/main.do?autoSearch=true&textCrpNm=${code}`,
  };
  record.interpretation = classify(record, previous);
  return record;
}

const source = await readFile(new URL("../app/data.ts", import.meta.url), "utf8");
const companyNames = [...new Set([...source.matchAll(/st\("([^"]+)"/g)].map((match) => match[1]))].sort((a, b) => a.localeCompare(b, "ko"));

const listedStocks = (await Promise.all([getMarketStocks("KOSPI"), getMarketStocks("KOSDAQ")])).flat();
const codeByName = new Map(listedStocks.map((stock) => [stock.stockName, stock.itemCode]));
for (const [name, code] of Object.entries(CODE_OVERRIDES)) codeByName.set(name, code);
const unmatched = companyNames.filter((name) => !codeByName.has(name));

if (unmatched.length) {
  throw new Error(`종목코드 매칭 실패: ${unmatched.join(", ")}`);
}

const payloads = await parallelMap(companyNames, 10, async (company) => {
  const code = codeByName.get(company);
  const payload = await fetchJson(`${FINANCE_ENDPOINT}/${code}/finance/quarter`);
  return toRecord(company, code, payload);
});

const records = Object.fromEntries(payloads.map((record) => [record.company, record]));
const output = `// Generated by scripts/update-earnings.mjs on ${VERIFIED_AT}.\n` +
  `// Financial figures are quarterly, in KRW 100 million, and include only periods marked actual by the source.\n` +
  `// q1/q2 track whichever two quarters are current as of the run date (auto-computed, not hardcoded).\n` +
  `export type EarningsStatus = "확정" | "미발표";\n` +
  `export type EarningsQuarter = {\n` +
  `  period: string;\n  status: EarningsStatus;\n  revenue: number | null;\n  operatingProfit: number | null;\n  netIncome: number | null;\n  operatingMargin: number | null;\n};\n` +
  `export type EarningsRecord = {\n` +
  `  company: string;\n  code: string;\n  basis: "연결" | "별도·개별";\n  unit: "억원";\n  q1: EarningsQuarter;\n  q2: EarningsQuarter;\n` +
  `  comparisons: { q1RevenueQoq: number | null; q1OperatingProfitQoq: number | null; q2RevenueYoy: number | null; q2RevenueQoq: number | null; q2OperatingProfitYoy: number | null; q2OperatingProfitQoq: number | null };\n` +
  `  interpretation: string;\n  verifiedAt: string;\n  sourceLabel: string;\n  sourceUrl: string;\n  dartUrl: string;\n};\n\n` +
  `export const earningsByStock: Record<string, EarningsRecord> = ${JSON.stringify(records, null, 2)};\n`;

await writeFile(new URL("../app/earnings-data.ts", import.meta.url), output);

const confirmedQ2 = payloads.filter((record) => record.q2.status === "확정").length;
const missingQ2 = payloads.filter((record) => record.q2.status !== "확정").map((record) => record.company);
console.log(JSON.stringify({ trackedQuarters: { q1: Q1, q2: Q2 }, companies: companyNames.length, confirmedQ2, missingQ2 }, null, 2));
