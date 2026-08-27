#!/usr/bin/env python3
"""
OpenDART 공시검색 API로 companies.json에 등록된 기업들의
최근 공시를 수집해 data/raw_dart.json에 저장한다.

DART/IR 공시는 그 자체로 '확정' 등급으로 취급한다(신뢰도 최상위).
정정 공시(rm에 '정정' 포함)는 원본 이슈를 지우지 않고
별도 플래그로 표시할 수 있도록 is_correction 필드를 붙여둔다.

사용법:
    python scripts/collect_dart.py --days 2
환경변수:
    OPENDART_API_KEY
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parent.parent
COMPANIES_PATH = ROOT / "data" / "companies.json"
OUTPUT_PATH = ROOT / "data" / "raw_dart.json"

DART_LIST_URL = "https://opendart.fss.or.kr/api/list.json"

# 사람이 승인해야 하는 '핵심 투자모멘텀'과 자동등록 가능한 공시를 구분하기 위한
# 대략적인 1차 카테고리 매핑. report_nm(보고서명)에 포함된 키워드로 판정한다.
# 정교한 분류는 scripts/dedup_classify.py에서 한 번 더 수행한다.
REPORT_KEYWORDS = {
    "실적": ["잠정실적", "분기보고서", "반기보고서", "사업보고서", "실적"],
    "수주": ["공급계약", "수주"],
    "증설": ["증설", "공장", "설비투자", "시설투자"],
    "기술": ["특허", "인증"],
    "정책": ["보조금"],
    "자본": ["유상증자", "무상증자", "전환사채", "신주인수권", "자기주식", "배당"],
    "바이오": ["임상", "기술이전", "품목허가"],
    "리스크": ["소송", "계약해지", "감사의견", "관리종목", "상장폐지"],
}


def guess_category(report_nm: str) -> str:
    for category, keywords in REPORT_KEYWORDS.items():
        if any(kw in report_nm for kw in keywords):
            return category
    return "기타"


def fetch_disclosures(api_key: str, corp_code: str, bgn_de: str, end_de: str) -> list:
    params = {
        "crtfc_key": api_key,
        "corp_code": corp_code,
        "bgn_de": bgn_de,
        "end_de": end_de,
        "page_no": "1",
        "page_count": "100",
    }
    url = f"{DART_LIST_URL}?{urlencode(params)}"
    with urlopen(url, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    # status "013"은 '조회된 데이터가 없습니다' — 정상 케이스이므로 빈 리스트 반환
    if data.get("status") not in ("000", "013"):
        print(f"⚠️ DART 응답 오류 corp_code={corp_code}: {data.get('message')}", file=sys.stderr)
        return []

    return data.get("list", [])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=2, help="최근 며칠치를 조회할지 (cron 주기보다 넉넉하게)")
    args = parser.parse_args()

    api_key = os.environ.get("OPENDART_API_KEY")
    if not api_key:
        print("OPENDART_API_KEY 환경변수가 없습니다.", file=sys.stderr)
        sys.exit(1)

    companies = json.loads(COMPANIES_PATH.read_text(encoding="utf-8"))["companies"]

    end_de = datetime.now().strftime("%Y%m%d")
    bgn_de = (datetime.now() - timedelta(days=args.days)).strftime("%Y%m%d")

    results = []
    for c in companies:
        corp_code = c.get("corp_code")
        if not corp_code:
            print(f"⚠️ {c['name']}: corp_code 없음 — lookup_corp_code.py 먼저 실행 필요", file=sys.stderr)
            continue

        items = fetch_disclosures(api_key, corp_code, bgn_de, end_de)
        for item in items:
            report_nm = item.get("report_nm", "")
            rm = item.get("rm", "")
            results.append({
                "company": c["name"],
                "stock_code": c["stock_code"],
                "sector": c["sector"],
                "source_type": "dart",
                "confidence": "확정",  # DART 공시는 항상 확정
                "category": guess_category(report_nm),
                "title": report_nm,
                "rcept_no": item.get("rcept_no"),
                "rcept_dt": item.get("rcept_dt"),
                "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={item.get('rcept_no')}",
                "is_correction": "정정" in report_nm or "정정" in rm,
            })
        time.sleep(0.2)  # API 과다호출 방지용 최소 간격

    OUTPUT_PATH.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"DART 공시 {len(results)}건 수집 완료 → {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
