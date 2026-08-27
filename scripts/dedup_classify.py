#!/usr/bin/env python3
"""
raw_dart.json + raw_news.json을 합쳐서
  1) 같은 사안을 다룬 여러 기사를 하나의 이슈로 묶고 (중복제거)
  2) 카테고리(실적/수주/증설/기술/정책/자본/바이오/리스크)를 규칙기반으로 분류하고
  3) 신뢰도(확정/미확인/교차검증)를 판정하고
  4) 헤드라인 vs 본문 언급 여부로 '단순언급'과 '실제 모멘텀 후보'를 구분하고
  5) 기존 이슈 저장소(data/issues_store.json)에 누적 병합한다.

★ 중요한 한계 (README에도 적어둠) ★
이건 전부 규칙/키워드 기반 휴리스틱이다. 특히:
  - 제목 유사도로 기사를 묶는 로직은 완벽하지 않다 (다른 사안인데 묶이거나,
    같은 사안인데 못 묶일 수 있음)
  - 긍정/중립/부정 판정은 아주 단순한 키워드 사전 기반이라 오판이 흔하다
  - '단순언급 vs 실제 모멘텀'도 제목 등장 여부라는 거친 기준일 뿐이다
이 스크립트가 만든 결과 중 direction(긍정/부정)이 붙거나
needs_approval=true인 항목, 즉 '핵심 투자모멘텀'에 영향을 줄 수 있는
항목은 사람이 검토 후 승인하는 걸 전제로 설계했다. 공시(DART)는 항상
확정으로 자동등록해도 되지만, 뉴스 기반 판단은 그대로 믿지 말 것.

사용법:
    python scripts/dedup_classify.py
"""
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DART_PATH = ROOT / "data" / "raw_dart.json"
RAW_NEWS_PATH = ROOT / "data" / "raw_news.json"
STORE_PATH = ROOT / "data" / "issues_store.json"

STALE_DAYS = 60

CATEGORY_KEYWORDS = {
    "실적": ["잠정실적", "실적", "매출", "영업이익", "컨센서스", "분기보고서"],
    "수주": ["수주", "공급계약", "고객사", "수주잔고"],
    "증설": ["증설", "캐파", "CAPEX", "신규 공장", "가동률", "설비투자"],
    "기술": ["신제품", "양산", "수율", "인증", "특허"],
    "정책": ["보조금", "규제", "관세", "정부"],
    "자본": ["유상증자", "전환사채", "자사주", "배당", "무상증자"],
    "바이오": ["임상", "FDA", "기술이전", "품목허가"],
    "리스크": ["소송", "계약해지", "실적둔화", "적자", "감사의견", "리콜"],
}

POSITIVE_WORDS = ["최대", "사상 최대", "확대", "상향", "흑자전환", "신기록", "체결", "승인", "개발 성공", "역대"]
NEGATIVE_WORDS = ["하향", "감소", "적자", "소송", "리콜", "지연", "철회", "경고", "부진", "해지", "축소"]


def guess_category(text: str) -> str:
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return category
    return "기타"


def guess_direction(text: str) -> str:
    pos = any(w in text for w in POSITIVE_WORDS)
    neg = any(w in text for w in NEGATIVE_WORDS)
    if pos and not neg:
        return "긍정"
    if neg and not pos:
        return "부정"
    return "중립"


def tokenize(text: str) -> set:
    # 아주 단순한 토큰화: 한글/영문/숫자 덩어리만 추출. 형태소분석기 없이 돌아가게 하려는 절충안.
    return set(re.findall(r"[가-힣A-Za-z0-9]+", text))


def title_similarity(a: str, b: str) -> float:
    ta, tb = tokenize(a), tokenize(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)  # 자카드 유사도


def cluster_news(news_items: list, threshold: float = 0.4) -> list:
    """같은 회사의 뉴스 중 제목이 threshold 이상 비슷하면 하나의 클러스터로 묶는다.

    클러스터의 '첫 기사'하고만 비교하면 3개 이상 기사가 조금씩 다른 표현을
    쓸 때(A~B는 비슷, B~C는 비슷, A~C는 덜 비슷) 같은 사안인데도 못 묶이는
    경우가 많아서, 클러스터 안의 아무 기사와나 threshold 이상이면 합류시킨다
    (single-linkage 방식). 여전히 완벽하지 않으니 실제 운영하면서 threshold를
    조정하거나 더 나은 유사도 로직으로 교체하는 걸 권장한다.
    """
    clusters = []  # each: {"items": [...]}
    for item in news_items:
        placed = False
        for cluster in clusters:
            same_company = cluster["items"][0]["company"] == item["company"]
            best_sim = max(title_similarity(existing["title"], item["title"]) for existing in cluster["items"])
            if same_company and best_sim >= threshold:
                cluster["items"].append(item)
                placed = True
                break
        if not placed:
            clusters.append({"items": [item]})
    return clusters


def build_issue_from_news_cluster(cluster: list) -> dict:
    items = cluster["items"]
    rep = items[0]
    full_text = " ".join(i["title"] + " " + i.get("summary", "") for i in items)
    press_set = {i["press"] for i in items if i.get("press")}

    confidence = "교차검증" if len(press_set) >= 2 else "미확인"
    in_headline = any(rep["company"] in i["title"] for i in items)

    return {
        "company": rep["company"],
        "stock_code": rep["stock_code"],
        "sector": rep["sector"],
        "category": guess_category(full_text),
        "direction": guess_direction(full_text),
        "confidence": confidence,
        "is_mere_mention": not in_headline,  # True면 '단순언급' 후보 -> 모멘텀 큐에서 제외
        "headline": rep["title"],
        "source_type": "news",
        "sources": [{"press": i["press"], "url": i["url"], "pub_date": i.get("pub_date")} for i in items],
        "source_count": len(items),
    }


def build_issue_from_dart(item: dict) -> dict:
    return {
        "company": item["company"],
        "stock_code": item["stock_code"],
        "sector": item["sector"],
        "category": item["category"],
        "direction": guess_direction(item["title"]),
        "confidence": "확정",
        "is_mere_mention": False,
        "headline": item["title"],
        "source_type": "dart",
        "sources": [{"press": "DART", "url": item["url"], "pub_date": item.get("rcept_dt")}],
        "source_count": 1,
        "is_correction": item.get("is_correction", False),
        "rcept_no": item.get("rcept_no"),
    }


def load_json(path: Path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def merge_into_store(candidates: list, store: dict) -> dict:
    today = datetime.now().strftime("%Y-%m-%d")
    issues = store.setdefault("issues", [])

    for cand in candidates:
        match = None
        for existing in issues:
            if (existing["company"] == cand["company"]
                    and existing["category"] == cand["category"]
                    and title_similarity(existing["headline"], cand["headline"]) >= 0.4):
                match = existing
                break

        if match:
            # 기존 이슈 업데이트: 신뢰도 승격, 소스 추가, 최종 업데이트일 갱신
            existing_urls = {s["url"] for s in match["sources"]}
            for s in cand["sources"]:
                if s["url"] not in existing_urls:
                    match["sources"].append(s)
            match["source_count"] = len(match["sources"])
            if cand["confidence"] == "확정" or match["confidence"] != "확정":
                # 확정(DART) > 교차검증 > 미확인 순으로 신뢰도는 내려가지 않게만 갱신
                rank = {"미확인": 0, "교차검증": 1, "확정": 2}
                if rank[cand["confidence"]] > rank.get(match["confidence"], 0):
                    match["confidence"] = cand["confidence"]
                elif len({s["press"] for s in match["sources"] if s["press"] != "DART"}) >= 2 and match["confidence"] == "미확인":
                    match["confidence"] = "교차검증"
            match["last_updated"] = today
            match["stale"] = False
            if cand.get("is_correction"):
                match["status"] = "정정됨"
        else:
            cand["id"] = f"{cand['stock_code']}-{cand['category']}-{len(issues)+1}-{today.replace('-', '')}"
            cand["first_seen"] = today
            cand["last_updated"] = today
            cand["status"] = "정정됨" if cand.get("is_correction") else "일반"
            cand["stale"] = False
            issues.append(cand)

    # 60일 이상 갱신 없는 이슈 -> '모멘텀 점검 필요' 플래그
    cutoff = datetime.now() - timedelta(days=STALE_DAYS)
    for issue in issues:
        last_updated = datetime.strptime(issue["last_updated"], "%Y-%m-%d")
        issue["stale"] = last_updated < cutoff

    store["generated_at"] = today
    return store


def main():
    raw_dart = load_json(RAW_DART_PATH, [])
    raw_news = load_json(RAW_NEWS_PATH, [])
    store = load_json(STORE_PATH, {"issues": []})

    dart_issues = [build_issue_from_dart(i) for i in raw_dart]

    # 회사별로 묶어서 뉴스 클러스터링 (다른 회사끼리 잘못 묶이는 것 방지)
    by_company = {}
    for item in raw_news:
        by_company.setdefault(item["company"], []).append(item)

    news_issues = []
    for company_items in by_company.values():
        for cluster in cluster_news(company_items):
            news_issues.append(build_issue_from_news_cluster(cluster))

    # 모멘텀 큐에 넣지 않을 '단순언급'은 별도 카운트만 하고 그대로 store에는 남긴다
    # (완전히 버리지 않는 이유: 나중에 같은 회사 이슈가 더 쌓이면 재평가할 수 있어야 함)
    all_candidates = dart_issues + news_issues

    store = merge_into_store(all_candidates, store)
    STORE_PATH.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")

    momentum_candidates = [i for i in store["issues"] if not i.get("is_mere_mention") and i["direction"] != "중립"]
    stale = [i for i in store["issues"] if i.get("stale")]

    print(f"이슈 저장소 총 {len(store['issues'])}건")
    print(f"  - 이번 실행 신규/갱신 후보: {len(all_candidates)}건 (DART {len(dart_issues)} / 뉴스클러스터 {len(news_issues)})")
    print(f"  - 핵심모멘텀 승인 후보(방향성 있음+단순언급 아님): {len(momentum_candidates)}건 -> 사람 승인 필요")
    print(f"  - 60일 이상 갱신 없음('모멘텀 점검 필요'): {len(stale)}건")


if __name__ == "__main__":
    main()
