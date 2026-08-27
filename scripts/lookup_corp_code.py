#!/usr/bin/env python3
"""
OpenDART의 corpCode.xml(전체 상장사 고유번호 목록)을 내려받아
data/companies.json 안의 종목들에 corp_code를 채워넣는다.

OpenDART는 종목코드(stock_code)가 아니라 자체 corp_code(8자리)로
공시를 조회하기 때문에, 공시 수집 전에 반드시 한 번 실행해야 한다.
corpCode.xml 자체는 거의 매일 바뀌지 않으므로 data/corpCode_cache.xml로
캐싱해서 매 실행마다 다시 받지 않는다(파일이 있으면 재사용).

사용법:
    python scripts/lookup_corp_code.py
환경변수:
    OPENDART_API_KEY  - OpenDART에서 발급받은 API 키
"""
import io
import json
import os
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parent.parent
COMPANIES_PATH = ROOT / "data" / "companies.json"
CACHE_PATH = ROOT / "data" / "corpCode_cache.xml"

DART_CORPCODE_URL = "https://opendart.fss.or.kr/api/corpCode.xml"


def fetch_corpcode_xml(api_key: str) -> bytes:
    if CACHE_PATH.exists():
        return CACHE_PATH.read_bytes()

    url = f"{DART_CORPCODE_URL}?{urlencode({'crtfc_key': api_key})}"
    with urlopen(url, timeout=30) as resp:
        zip_bytes = resp.read()

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        # 압축 안에 CORPCODE.xml 하나만 들어있음
        xml_name = zf.namelist()[0]
        xml_bytes = zf.read(xml_name)

    CACHE_PATH.write_bytes(xml_bytes)
    return xml_bytes


def build_stock_code_index(xml_bytes: bytes) -> dict:
    root = ET.fromstring(xml_bytes)
    index = {}
    for item in root.findall("list"):
        stock_code = (item.findtext("stock_code") or "").strip()
        corp_code = (item.findtext("corp_code") or "").strip()
        if stock_code:
            index[stock_code] = corp_code
    return index


def main():
    api_key = os.environ.get("OPENDART_API_KEY")
    if not api_key:
        print("OPENDART_API_KEY 환경변수가 없습니다.", file=sys.stderr)
        sys.exit(1)

    companies = json.loads(COMPANIES_PATH.read_text(encoding="utf-8"))
    xml_bytes = fetch_corpcode_xml(api_key)
    index = build_stock_code_index(xml_bytes)

    updated = 0
    missing = []
    for c in companies["companies"]:
        code = index.get(c["stock_code"])
        if code:
            if c.get("corp_code") != code:
                c["corp_code"] = code
                updated += 1
        else:
            missing.append(c["name"])

    COMPANIES_PATH.write_text(
        json.dumps(companies, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"corp_code {updated}건 갱신 완료.")
    if missing:
        print("⚠️ 매칭 실패(종목코드 확인 필요):", ", ".join(missing), file=sys.stderr)


if __name__ == "__main__":
    main()
