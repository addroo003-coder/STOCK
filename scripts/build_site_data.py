#!/usr/bin/env python3
"""
issues_store.json(누적된 이슈 원장)을 실제 사이트가 읽을 수 있는 형태로 두 파일로 나눠 만든다.

  1) data/site_data.json
     섹터 -> 세부산업 -> 종목 -> 모멘텀정보(이슈 타임라인) 구조.
     공시/뉴스 이슈는 여기에 '자동'으로 올라간다 (GPT 원안의 "공시·뉴스는 자동 등록" 원칙).
     각 이슈에는 confidence(확정/교차검증/미확인/정정됨), category, direction, sources가 그대로 붙어있어서
     프론트엔드에서 신뢰도 배지를 그릴 수 있다.

  2) data/pending_approval.json
     '핵심 투자모멘텀' 승인 대기열. direction이 긍정/부정이고 단순언급이 아닌 이슈,
     즉 기존 투자논리(핵심테제·상승촉매·핵심리스크)를 흔들 수 있는 이슈만 여기 올라온다.
     성혁님이 이 파일을 보고 실제로 투자관점 텍스트를 바꿀지 결정 -> 승인한 항목의 id를
     data/approved_log.json에 추가하면 다음 실행부터는 대기열에서 빠진다(중복 승인 요청 방지).

사용법:
    python scripts/build_site_data.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPANIES_PATH = ROOT / "data" / "companies.json"
STORE_PATH = ROOT / "data" / "issues_store.json"
APPROVED_LOG_PATH = ROOT / "data" / "approved_log.json"
SITE_DATA_PATH = ROOT / "data" / "site_data.json"
PENDING_PATH = ROOT / "data" / "pending_approval.json"


def load_json(path: Path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def main():
    companies = load_json(COMPANIES_PATH, {"companies": []})["companies"]
    store = load_json(STORE_PATH, {"issues": []})
    approved_ids = set(load_json(APPROVED_LOG_PATH, {"approved_ids": []})["approved_ids"])

    # 종목 메타(섹터/세부산업)를 stock_code 기준으로 빠르게 찾기 위한 인덱스
    meta_by_code = {c["stock_code"]: c for c in companies}

    site_data = {}  # sector -> sub_industry -> company -> [issues...]
    for issue in store["issues"]:
        meta = meta_by_code.get(issue["stock_code"], {})
        sector = meta.get("sector", issue.get("sector", "미분류"))
        sub_industry = meta.get("sub_industry", "미분류")

        site_data.setdefault(sector, {}).setdefault(sub_industry, {}).setdefault(issue["company"], [])
        site_data[sector][sub_industry][issue["company"]].append({
            "id": issue["id"],
            "category": issue["category"],
            "direction": issue["direction"],
            "confidence": issue["confidence"],
            "status": issue.get("status", "일반"),
            "headline": issue["headline"],
            "sources": issue["sources"],
            "first_seen": issue["first_seen"],
            "last_updated": issue["last_updated"],
            "stale": issue.get("stale", False),
        })

    # 종목별로 최신순 정렬
    for sector in site_data.values():
        for sub in sector.values():
            for company_issues in sub.values():
                company_issues.sort(key=lambda x: x["last_updated"], reverse=True)

    SITE_DATA_PATH.write_text(json.dumps(site_data, ensure_ascii=False, indent=2), encoding="utf-8")

    pending = [
        issue for issue in store["issues"]
        if issue["direction"] != "중립"
        and not issue.get("is_mere_mention")
        and issue["id"] not in approved_ids
    ]
    PENDING_PATH.write_text(json.dumps(pending, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"site_data.json 생성 완료 (섹터 {len(site_data)}개)")
    print(f"pending_approval.json: 승인 대기 {len(pending)}건")


if __name__ == "__main__":
    main()
