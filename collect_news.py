#!/usr/bin/env python3
"""
NAVER 뉴스 검색 API로 companies.json에 등록된 기업들의 최신 뉴스를 모아
data/raw_news.json에 저장한다.

기본값은 2027-06-30 이후에도 계속 쓸 수 있는 NAVER API HUB 경로
(naverapihub.apigw.ntruss.com)를 사용한다. 아직 기존 개발자센터 키만
있다면 --legacy 옵션으로 기존 openapi.naver.com 경로를 쓸 수 있다
(2027-06-30까지만 유효하니 결국엔 HUB로 옮겨야 함).

주의: 이 스크립트는 '수집'만 한다. 동일 사안을 여러 매체가 받아쓴
기사를 하나로 묶는 중복제거와 '단순언급 vs 실제 모멘텀' 판별은
scripts/dedup_classify.py에서 처리한다. 여기서는 원문을 그대로
저장하고, description(네이버가 준 요약 문장)만 남기고 기사 본문
전체는 절대 가져오지 않는다(저작권 보호).

사용법:
    python scripts/collect_news.py --display 20
환경변수 (HUB 방식, 기본값):
    NAVER_APIGW_KEY_ID
    NAVER_APIGW_KEY
환경변수 (--legacy 방식):
    NAVER_CLIENT_ID
    NAVER_CLIENT_SECRET
"""
import argparse
import json
import os
import re
import sys
import time
from html import unescape
from pathlib import Path
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
COMPANIES_PATH = ROOT / "data" / "companies.json"
OUTPUT_PATH = ROOT / "data" / "raw_news.json"

HUB_URL = "https://naverapihub.apigw.ntruss.com/search/v1/news"
LEGACY_URL = "https://openapi.naver.com/v1/search/news.json"

TAG_RE = re.compile(r"<[^>]+>")


def strip_tags(text: str) -> str:
    return unescape(TAG_RE.sub("", text or "")).strip()


def press_from_url(url: str) -> str:
    try:
        return urlparse(url).netloc
    except Exception:
        return ""


def build_request(query: str, display: int, legacy: bool) -> Request:
    params = {"query": query, "display": str(display), "sort": "date"}
    if legacy:
        url = f"{LEGACY_URL}?{urlencode(params)}"
        client_id = os.environ.get("NAVER_CLIENT_ID")
        client_secret = os.environ.get("NAVER_CLIENT_SECRET")
        if not client_id or not client_secret:
            print("NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 환경변수가 없습니다.", file=sys.stderr)
            sys.exit(1)
        headers = {
            "X-Naver-Client-Id": client_id,
            "X-Naver-Client-Secret": client_secret,
        }
    else:
        url = f"{HUB_URL}?{urlencode(params)}"
        key_id = os.environ.get("NAVER_APIGW_KEY_ID")
        key = os.environ.get("NAVER_APIGW_KEY")
        if not key_id or not key:
            print("NAVER_APIGW_KEY_ID / NAVER_APIGW_KEY 환경변수가 없습니다.", file=sys.stderr)
            sys.exit(1)
        headers = {
            "X-NCP-APIGW-API-KEY-ID": key_id,
            "X-NCP-APIGW-API-KEY": key,
        }
    return Request(url, headers=headers)


def fetch_news(query: str, display: int, legacy: bool) -> list:
    req = build_request(query, display, legacy)
    with urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("items", [])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--display", type=int, default=20, help="종목당 가져올 기사 수(최대 100)")
    parser.add_argument("--legacy", action="store_true", help="기존 openapi.naver.com 경로 사용")
    args = parser.parse_args()

    companies = json.loads(COMPANIES_PATH.read_text(encoding="utf-8"))["companies"]

    results = []
    for c in companies:
        query = c["name"]  # 회사명 기준 검색. 오탐이 많으면 aliases 중 더 구체적인 이름으로 좁힐 것.
        try:
            items = fetch_news(query, args.display, args.legacy)
        except Exception as e:
            print(f"⚠️ {c['name']} 뉴스 수집 실패: {e}", file=sys.stderr)
            continue

        for item in items:
            link = item.get("originallink") or item.get("link")
            results.append({
                "company": c["name"],
                "stock_code": c["stock_code"],
                "sector": c["sector"],
                "source_type": "news",
                "confidence": "미확인",  # 언론 단독보도는 기본 '미확인'. 교차검증은 dedup_classify.py에서 승격.
                "title": strip_tags(item.get("title")),
                "summary": strip_tags(item.get("description")),
                "press": press_from_url(link),
                "url": link,
                "pub_date": item.get("pubDate"),
            })
        time.sleep(0.1)

    OUTPUT_PATH.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"뉴스 {len(results)}건 수집 완료 → {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
