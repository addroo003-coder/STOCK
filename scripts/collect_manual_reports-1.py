#!/usr/bin/env python3
"""
성혁님이 구글 폼으로 직접 올린 리포트/코멘트를 모아
  - data/raw_manual.json (유형=이슈) : 종목 상세의 "핵심 이슈 타임라인"에 다른 뉴스/공시와
    함께 쌓이는 항목
  - data/raw_company_analysis.json (유형=기업분석) : 종목 상세의 "기업분석 메모"에
    들어가는, 쌓이지 않고 항상 최신 내용으로 교체되는 항목
로 나눠서 저장한다.

구글 폼 -> 연결된 구글 시트 -> "웹에 게시"(CSV) 또는 공유 링크에서 얻은 CSV 링크를 읽어온다.
API 키나 로그인 없이, 공개 CSV 링크 하나만 있으면 된다 (완전 무료, 카드 불필요).

★ 구글 폼 질문은 아래 6개가 전부 들어있으면 된다 (순서는 상관없음 — 질문 "제목"에
   들어있는 글자로 열을 찾기 때문) ★
    - 종목명     (단답형, 필수) - 사이트에 쓰이는 정확한 종목명과 똑같이 입력
    - 유형       (객관식: 이슈 / 기업분석, 필수)
    - 제목       (단답형, 필수)
    - 내용       (장문형, 필수)
    - 투자의견   (객관식: 긍정 / 중립 / 부정, 필수)
    - 참고 링크  (단답형, 선택)

환경변수:
    MANUAL_REPORTS_CSV_URL - 구글 시트 CSV 링크.
                             설정 안 되어 있으면 에러 내지 않고 그냥 건너뛴다
                             (아직 폼을 안 만들었어도 전체 파이프라인은 평소처럼 돈다).

사용법:
    python scripts/collect_manual_reports.py
"""
import csv
import io
import json
import os
import re
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent
COMPANIES_PATH = ROOT / "data" / "companies.json"
ISSUES_OUTPUT_PATH = ROOT / "data" / "raw_manual.json"
ANALYSIS_OUTPUT_PATH = ROOT / "data" / "raw_company_analysis.json"

VALID_DIRECTIONS = {"긍정", "중립", "부정"}

# 구글 시트 타임스탬프 로케일에 따라 "2026/10/20 10:05:28"이나
# "2026. 10. 20 오전 10:05:28"처럼 구분자/형식이 달라질 수 있어서,
# 맨 앞의 연/월/일 숫자 3덩어리만 느슨하게 뽑아낸다 (시간 표기는 날짜 표시용으로는
# 필요 없음).
TIMESTAMP_DATE_RE = re.compile(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})")


def parse_timestamp_date(timestamp: str) -> str:
    if not timestamp:
        return ""
    match = TIMESTAMP_DATE_RE.match(timestamp.strip())
    if not match:
        return ""
    year, month, day = match.groups()
    return f"{year}-{int(month):02d}-{int(day):02d}"


def normalize(name: str) -> str:
    return (name or "").strip().replace(" ", "")


def build_company_index(companies: list) -> dict:
    index = {}
    for c in companies:
        index[normalize(c["name"])] = c
        for alias in c.get("aliases", []):
            index[normalize(alias)] = c
    return index


def find_header(fieldnames: list, *keywords: str):
    for name in fieldnames:
        if any(kw in name for kw in keywords):
            return name
    return None


def write_empty(reason: str) -> None:
    print(reason)
    ISSUES_OUTPUT_PATH.write_text("[]", encoding="utf-8")
    ANALYSIS_OUTPUT_PATH.write_text("[]", encoding="utf-8")


def main():
    csv_url = os.environ.get("MANUAL_REPORTS_CSV_URL", "").strip()
    if not csv_url:
        write_empty("ℹ️ MANUAL_REPORTS_CSV_URL이 설정되지 않아 자체 리포트 수집을 건너뜁니다.")
        return

    try:
        with urlopen(csv_url, timeout=20) as resp:
            raw = resp.read().decode("utf-8-sig")
    except URLError as e:
        print(f"⚠️ 구글 시트 CSV를 가져오지 못했습니다: {e}", file=sys.stderr)
        write_empty("자체 리포트 수집 실패 - 빈 결과로 처리합니다 (다음 실행에서 재시도).")
        return

    companies = json.loads(COMPANIES_PATH.read_text(encoding="utf-8"))["companies"]
    company_index = build_company_index(companies)

    reader = csv.DictReader(io.StringIO(raw))
    fieldnames = reader.fieldnames or []
    col_timestamp = find_header(fieldnames, "타임스탬프", "Timestamp") or (fieldnames[0] if fieldnames else None)
    col_company = find_header(fieldnames, "종목")
    col_type = find_header(fieldnames, "유형")
    col_title = find_header(fieldnames, "제목")
    col_body = find_header(fieldnames, "내용")
    col_direction = find_header(fieldnames, "의견")
    col_url = find_header(fieldnames, "링크")

    if not (col_company and col_title and col_body and col_direction):
        write_empty("⚠️ 구글 시트 열 이름을 인식하지 못했습니다 (종목명/제목/내용/투자의견 문항을 확인하세요).")
        return

    issues = []
    analyses = []
    skipped = []
    for row in reader:
        raw_name = (row.get(col_company) or "").strip()
        row_type = (row.get(col_type) or "").strip() if col_type else "이슈"
        title = (row.get(col_title) or "").strip()
        body = (row.get(col_body) or "").strip()
        direction = (row.get(col_direction) or "").strip()
        url = (row.get(col_url) or "").strip() if col_url else ""
        timestamp = (row.get(col_timestamp) or "").strip() if col_timestamp else ""

        if not raw_name or not title:
            continue

        company = company_index.get(normalize(raw_name))
        if not company:
            skipped.append(raw_name)
            continue

        if direction not in VALID_DIRECTIONS:
            direction = "중립"

        timestamp_date = parse_timestamp_date(timestamp)

        entry = {
            "company": company["name"],
            "stock_code": company["stock_code"],
            "sector": company["sector"],
            "title": title,
            "body": body,
            "direction": direction,
            "url": url or None,
            "timestamp": timestamp,
            "timestamp_date": timestamp_date,
        }

        if "기업분석" in row_type:
            analyses.append(entry)
        else:
            issues.append(entry)

    ISSUES_OUTPUT_PATH.write_text(json.dumps(issues, ensure_ascii=False, indent=2), encoding="utf-8")
    ANALYSIS_OUTPUT_PATH.write_text(json.dumps(analyses, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"자체 이슈 리포트 {len(issues)}건, 기업분석 메모 {len(analyses)}건 수집 완료")
    if skipped:
        print(f"⚠️ 종목명을 못 찾아서 건너뜀(폼에 적은 이름을 확인하세요): {', '.join(skipped)}", file=sys.stderr)


if __name__ == "__main__":
    main()
