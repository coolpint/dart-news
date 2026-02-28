# DART Disclosure Insights (KOSPI/KOSDAQ)

유가증권시장(KOSPI) + 코스닥(KOSDAQ) 상장기업의 DART 공시를 매일 분석해서,
중장기 펀더멘털 관점의 심층 기사를 자동 생성하고 Slack으로 배포하는 도구입니다.

## What it does

1. DART `todayRSS.xml` 수집
2. 회사-시장 매핑으로 대상 시장(KOSPI/KOSDAQ) 공시 필터링
3. 공시 유형/재무 단서 기반 중요도 스코어링
4. 하루 Top1 기본, 조건 충족 시 Top2 선택
5. 애널리스트/경제부 기자 스타일 기사 자동 작성
6. 지정 Slack 채널로 자동 발행

## Project structure

- `dart_digest/dart_client.py`: RSS 수집/파싱
- `dart_digest/market_filter.py`: 시장 필터(KOSPI/KOSDAQ 등)
- `dart_digest/scoring.py`: 중요도 평가
- `dart_digest/article_writer.py`: 기사 생성 (OpenAI 옵션 + 템플릿 폴백)
- `dart_digest/slack_client.py`: Slack 전송
- `dart_digest/pipeline.py`: 전체 오케스트레이션
- `dart_digest/storage.py`: SQLite 저장(중복 방지/이력)
- `dart_digest/cli.py`: CLI 엔트리포인트

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
```

환경변수 적용 후 실행:

```bash
set -a
source .env
set +a
python3 -m dart_digest.cli run --dry-run --print-article
```

정상 동작 확인 후 Slack 배포:

```bash
python3 -m dart_digest.cli run
```

## Run on GitHub Actions

워크플로 파일은 `/.github/workflows/dart-digest.yml`로 포함되어 있습니다.

1. GitHub 저장소에 코드를 푸시합니다.
2. 저장소 Settings > Secrets and variables > Actions에 아래 시크릿을 등록합니다.
   - `SLACK_WEBHOOK_URL` (권장: 필수)
   - `SLACK_CHANNEL` (선택)
   - `OPENAI_API_KEY` (선택)
3. Actions 탭에서 `DART Daily Insights` 워크플로를 수동 실행(`Run workflow`)해 검증합니다.
4. 문제 없으면 스케줄 실행을 사용합니다. 기본 스케줄은 `매일 10:10 KST, 18:10 KST`입니다.

로컬에서 GitHub 업로드:

```bash
git init
git add .
git commit -m "Initial DART disclosure insights pipeline"
git branch -M main
git remote add origin <YOUR_GITHUB_REPO_URL>
git push -u origin main
```

## Data requirements

`DART_COMPANY_MAP_PATH` CSV는 아래 컬럼을 반드시 포함해야 합니다.

- `company_name`
- `ticker`
- `market` (`KOSPI`/`KOSDAQ` ...)

현재 `data/kospi_companies_sample.csv`는 샘플입니다.
운영 시에는 전체 상장사 목록으로 교체하세요.

대상 시장은 `DART_TARGET_MARKETS`로 지정합니다.

- 예: `DART_TARGET_MARKETS=KOSPI,KOSDAQ`

## Selection rule

- 기본: 점수 1위 공시 1건
- 2건 허용 조건:
  - 2위 점수 >= `DART_SECOND_PICK_MIN_SCORE`
  - 1위-2위 점수 차 <= `DART_SECOND_PICK_MIN_GAP`
  - 이벤트 유형이 1위와 다름

## Deduplication

- 처리 이력이 있는 `receipt_no` 공시는 다음 실행에서 제외합니다.
- 따라서 같은 날 2회(10:10/18:10) 실행해도 이전에 본 공시는 다시 발행하지 않습니다.
- 강제 재처리가 필요하면 `--force` 옵션을 사용합니다.

## Scheduling

크론 예시(매일 10:10/18:10 KST):

```cron
10 10 * * * cd /Users/air/codes/dart && /Users/air/codes/dart/.venv/bin/python -m dart_digest.cli run >> /Users/air/codes/dart/data/dart_digest.log 2>&1
10 18 * * * cd /Users/air/codes/dart && /Users/air/codes/dart/.venv/bin/python -m dart_digest.cli run >> /Users/air/codes/dart/data/dart_digest.log 2>&1
```

## Notes

- 기사 생성은 OpenAI API 키가 있으면 LLM 기반으로 작성합니다.
- API 키가 없거나 실패하면 템플릿 기반 기사로 자동 폴백합니다.
- 출력 마지막에 투자권유 아님 면책 문구를 추가합니다.
