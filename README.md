# stock-atlas 자동화 (파일럿 · 18~20종목)

"AI 성장섹터 투자 나침반" 사이트의 종목별 "모멘텀정보"(최근 리포트·관련뉴스·판정)를
OpenDART 공시 + 네이버 뉴스로 자동 채우기 위한 스캐폴드입니다.
비용은 전부 무료 티어로 돌아가도록 설계했습니다(자세한 내용은 맨 아래 "비용" 참고).

## 지금 상태 (2026-08-27 기준)
- 실제 stock-atlas 프론트엔드 코드는 아직 이 저장소에 없습니다. ChatGPT Sites 캔버스에서
  코드를 내보내서 이 저장소에 합치는 작업이 먼저 필요합니다 (아래 0단계).
- 파일럿 종목은 18개만 등록했습니다 (`data/companies.json`) — AI반도체 섹터 16종목 전부 +
  GPT 원안에서 언급된 레인보우로보틱스·알테오젠. 나머지 섹터는 회사님이 실제 사이트의
  127종목 리스트를 주시면 그대로 확장할 수 있습니다.
- 종목코드는 기억을 바탕으로 채운 값이라 **사용 전 반드시 직접 검증**해주세요.

## 폴더 구조
```
data/
  companies.json        # 종목 별칭 테이블 (직접 관리)
  corpCode_cache.xml     # DART 고유번호 캐시 (자동 생성, git에는 안 올려도 됨)
  raw_dart.json          # 이번 실행에서 수집한 공시 원본 (자동 생성)
  raw_news.json          # 이번 실행에서 수집한 뉴스 원본 (자동 생성)
  issues_store.json      # 누적 이슈 원장 — 이력이 계속 쌓이는 핵심 데이터 (자동 생성/갱신)
  site_data.json         # 사이트가 읽을 최종 데이터 (자동 생성)
  pending_approval.json  # 핵심모멘텀 승인 대기열 (자동 생성)
  approved_log.json      # 승인 완료 이슈 id 기록 (직접 관리)
scripts/
  lookup_corp_code.py    # 종목코드 -> DART corp_code 매핑
  collect_dart.py        # OpenDART 공시 수집
  collect_news.py        # 네이버 뉴스 수집
  dedup_classify.py      # 중복제거 + 규칙기반 분류 + 이슈 원장 병합
  build_site_data.py     # 사이트용 JSON + 승인대기열 생성
.github/workflows/update.yml  # 매시 자동 실행 워크플로
```

## 0단계 — 사이트 코드 가져오기 (자동화 붙이기 전 필수)
현재 사이트는 ChatGPT Sites(`stock-atlas.codeblack123.chatgpt.site`)로 만들어져 있어서
외부(GitHub Actions)에서 데이터를 밀어넣을 공식적인 방법이 없습니다. ChatGPT 대화의
캔버스 화면에서 "코드 보기/복사" 기능으로 생성된 코드를 받아 이 저장소의 `site/` 같은
폴더에 넣고, 프론트엔드가 `data/site_data.json`을 읽어서 렌더링하도록 연결해주세요.
(이 부분은 실제 코드를 봐야 구체적으로 도와드릴 수 있어서, 내보낸 코드를 공유해주시면
다음 단계로 이어서 작업하겠습니다.)

## 1단계 — GitHub 저장소 만들기
- 새 **퍼블릭** 저장소를 만드세요 (퍼블릭이어야 GitHub Actions 분(分) 제한이 없고,
  GitHub Pages도 무료로 붙습니다).
- 이 폴더(`stock-atlas-automation/`) 안의 내용을 그대로 푸시하세요.

## 2단계 — API 키 발급
- **OpenDART**: https://opendart.fss.or.kr 회원가입 후 "인증키 신청" → API 키 발급
- **NAVER 뉴스검색**: NAVER Cloud Platform 콘솔(NAVER API HUB)에서 Search API 사용 신청 →
  Access Key ID / Secret Key 발급. 예전 개발자센터(openapi.naver.com) 키가 이미 있다면
  2027-06-30까지는 그걸로도 되지만(`collect_news.py --legacy` 옵션 사용), 새로 만든다면
  처음부터 API HUB로 발급받는 걸 추천합니다.

## 3단계 — 저장소 Secrets 등록
GitHub 저장소 Settings → Secrets and variables → Actions 에서 아래 4개를 등록:
- `OPENDART_API_KEY`
- `NAVER_APIGW_KEY_ID`
- `NAVER_APIGW_KEY`
(레거시 경로를 쓴다면 `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`도 추가하고
`.github/workflows/update.yml`의 뉴스 수집 스텝에 `--legacy` 옵션을 붙이세요.)

## 4단계 — GitHub Pages 활성화
Settings → Pages → Source를 "GitHub Actions"(정적 사이트 코드가 준비되면) 또는
브랜치 배포 방식으로 설정하세요. 이건 0단계에서 사이트 코드를 붙인 뒤에 하면 됩니다.

## 5단계 — 첫 실행
Actions 탭 → "종목 이슈 자동 업데이트" → "Run workflow"로 수동 실행해서 정상 동작하는지
먼저 확인하세요. 이후에는 매시 자동으로 돕니다 (cron 주기는 `update.yml` 상단에서 조정 가능).

## 핵심모멘텀 승인 흐름
- 공시(DART)와 일반 뉴스는 자동으로 `site_data.json`에 올라갑니다. 신뢰도 배지
  (확정/교차검증/미확인/정정됨)가 같이 붙어있어서 프론트엔드에서 구분해 보여줄 수 있습니다.
- 기존 투자논리(핵심테제·상승촉매·핵심리스크)를 바꿀 만한 이슈, 즉 방향성(긍정/부정)이
  있고 단순언급이 아닌 이슈만 `data/pending_approval.json`에 따로 쌓입니다.
- 이 파일을 보고 실제로 투자관점 텍스트를 바꿀지 판단한 뒤, 승인한 이슈의 `id`를
  `data/approved_log.json`의 `approved_ids` 배열에 추가하고 커밋하면 다음 실행부터
  대기열에서 빠집니다.

## 로컬에서 미리 테스트하기
```bash
cd stock-atlas-automation
export OPENDART_API_KEY=...
export NAVER_APIGW_KEY_ID=...
export NAVER_APIGW_KEY=...
python scripts/lookup_corp_code.py
python scripts/collect_dart.py --days 2
python scripts/collect_news.py --display 20
python scripts/dedup_classify.py
python scripts/build_site_data.py
```

## 비용 — 전부 무료로 가능합니다
- **GitHub Actions**: 퍼블릭 저장소는 완전 무료·무제한. 매시 실행(하루 24회, 실행당 1분 내외)
  기준으로도 문제없음.
- **GitHub Pages**: 퍼블릭 저장소 무료.
- **OpenDART**: 무료(정확한 일일 호출 한도는 이용약관에 별도 명시가 안 되어 있어
  opendart.fss.or.kr 공지사항에서 최신 수치를 한 번 확인하는 걸 권장).
- **NAVER API HUB 뉴스검색**: 현재 무료(월 77.5만 건, 초당 50건 한도 — 18~127종목,
  시간당 1회 수준으로는 여유 있음). 다만 문서에 "향후 유료 전환 가능성" 문구가 있어
  나중에 바뀔 수 있음.
- **분류 로직**: 말씀하신 대로 LLM 없이 규칙기반(키워드 매칭)으로만 구현해서 API 호출
  비용이 전혀 없습니다. 대신 정확도는 낮은 편이라, 특히 긍정/부정 판정과 카테고리
  분류는 사람이 종종 확인해주는 걸 권장합니다 (그래서 승인 대기열 구조를 넣었습니다).
- 이 구조에서 유일하게 돈이 들 수 있는 지점은 ChatGPT Plus 요금제입니다(사이트 원본을
  ChatGPT Sites에서 계속 관리하려면 필요) — 하지만 코드를 내보내 GitHub Pages로 옮기면
  그 이후로는 사이트 운영 자체에 ChatGPT Plus가 필요하지 않습니다.

## 알려진 한계 (다음에 더 다듬어야 할 것)
- 종목 매칭이 회사명 단순 포함 검사 수준이라 계열사/제품명 오탐 가능성 있음
- 뉴스 제목 유사도 기반 클러스터링(자카드 유사도)은 형태소 분석기가 아니라서 정교하지 않음
- 긍정/부정 키워드 사전이 아주 작음 — 실제 운영하면서 계속 보강 필요
- `data/companies.json`의 종목코드/corp_code는 실제 값으로 재검증 필요
- NAVER API HUB의 정확한 엔드포인트 경로·파라미터는 공식 문서로 한 번 더 대조 확인 권장
  (인증 헤더명 `X-NCP-APIGW-API-KEY-ID` / `X-NCP-APIGW-API-KEY`는 NCP 공식 문서로 확인함)
