#!/usr/bin/env python3
"""
구글 뉴스 RSS(news.google.com/rss/search)로 companies.json에 등록된 기업들의
최신 뉴스를 모아 data/raw_news.json에 저장한다.

네이버 뉴스 API 대신 이걸 쓰는 이유: 네이버 쪽(개발자센터/API HUB)은
- 개발자센터: 2026-07-31부로 신규 신청 자체가 막힘
- API HUB(NCP): 결제수단(카드) 등록이 필수이고, 무료 한도를 넘으면 자동으로
  종량제 과금으로 넘어가는 구조라 완전 무료를 원하면 리스크가 있음
구글 뉴스 RSS는 API 키/가입/카드 등록이 전혀 필요 없고 완전 무료다.

★ 한계 (README에도 적어둠) ★
- 구글이 공식 문서화한 API가 아니라 언제든 예고 없이 바뀌거나 막힐 수 있음
- <description>에 네이버처럼 별도 요약 문장이 오는 게 아니라 제목을 다시
  감싼 HTML이 오는 경우가 많음 — 그래서 summary는 참고용 정도로만 쓸 것
- <link>가 news.google.com을 거치는 리다이렉트 링크라 원문 URL이 아님
  (그래서 언론사 구분은 URL 도메인이 아니라 <source> 태그로 함)
- 검색어 기반이라 네이버가 잡는 국내 매체 커버리지와 100% 같지 않을 수 있음

사용법:
    python scripts/collect_news.py --display 20 --when 2d
"""
import argparse
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from html import unescape
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
COMPANIES_PATH = ROOT / "data" / "companies.json"
OUTPUT_PATH = ROOT / "data" / "raw_news.json"

FEED_URL = "https://news.google.com/rss/search"
TAG_RE = re.compile(r"<[^>]+>")
USER_AGENT = "Mozilla/5.0 (compatible; stock-atlas-bot/1.0)"


def strip_tags(text: str) -> str:
    cleaned = unescape(TAG_RE.sub("", text or ""))
    return re.sub(r"\s+", " ", cleaned.replace("\xa0", " ")).strip()


def fetch_feed(query: str, when: str) -> bytes:
    q = f"{query} when:{when}" if when else query
    params = {"q": q, "hl": "ko", "gl": "KR", "ceid": "KR:ko"}
    url = f"{FEED_URL}?{urlencode(params)}"
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=15) as resp:
        return resp.read()


def parse_items(xml_bytes: bytes, display: int) -> list:
    root = ET.fromstring(xml_bytes)
    items = []
    for item in root.findall("./channel/item")[:display]:
        source_el = item.find("source")
        press = source_el.text.strip() if source_el is not None and source_el.text else ""
        items.append({
            "title": strip_tags(item.findtext("title")),
            "summary": strip_tags(item.findtext("description")),
            "press": press,
            "url": item.findtext("link"),
            "pub_date": item.findtext("pubDate"),
        })
    return items


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--display", type=int, default=20, help="종목당 가져올 기사 수(최대 100)")
    parser.add_argument("--when", default="2d", help="구글 뉴스 시간필터 (예: 1d, 2d, 7h). 비우려면 --when ''")
    args = parser.parse_args()

    companies = json.loads(COMPANIES_PATH.read_text(encoding="utf-8"))["companies"]

    results = []
    for c in companies:
        query = c["name"]  # 오탐이 많으면 aliases 중 더 구체적인 이름으로 좁힐 것.
        try:
            xml_bytes = fetch_feed(query, args.when)
            items = parse_items(xml_bytes, args.display)
        except (URLError, ET.ParseError) as e:
            print(f"⚠️ {c['name']} 뉴스 수집 실패: {e}", file=sys.stderr)
            continue

        for item in items:
            results.append({
                "company": c["name"],
                "stock_code": c["stock_code"],
                "sector": c["sector"],
                "source_type": "news",
                "confidence": "미확인",  # 언론 단독보도는 기본 '미확인'. 교차검증은 dedup_classify.py에서 승격.
                "title": item["title"],
                "summary": item["summary"],
                "press": item["press"],
                "url": item["url"],
                "pub_date": item["pub_date"],
            })
        time.sleep(0.3)  # 짧은 시간에 너무 많이 두드리지 않도록 (비공식 엔드포인트라 예의상)

    OUTPUT_PATH.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"뉴스 {len(results)}건 수집 완료 → {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
