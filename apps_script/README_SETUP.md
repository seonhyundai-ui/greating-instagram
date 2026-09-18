# Greating Instagram 자동화 v0.7.0

구조:

```text
Apps Script 08시대 / 19시대
        ↓ workflow_dispatch
GitHub Actions
        ↓
python -m scripts.daily_collect
        ↓
Meta API → Google Sheets → Streamlit
```

GitHub Actions의 `schedule`은 사용하지 않습니다. Apps Script가 실행 시각을 담당하고 GitHub Actions는 Python 실행 환경으로만 사용합니다.

## 1. GitHub workflow 설치

저장소 루트에 다음 파일을 추가합니다.

```text
.github/workflows/instagram_daily_collect.yml
```

## 2. GitHub Actions Secrets

Repository → Settings → Secrets and variables → Actions에 아래 3개 Secret을 등록합니다.

```text
DOTENV_B64
GOOGLE_OAUTH_CLIENT_B64
GOOGLE_TOKEN_B64
```

Windows PowerShell에서 Base64 값을 만드는 예시:

```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes(".env"))
[Convert]::ToBase64String([IO.File]::ReadAllBytes("credentials/google_oauth_client.json"))
[Convert]::ToBase64String([IO.File]::ReadAllBytes("credentials/google_token.json"))
```

출력값을 각각 대응하는 GitHub Secret에 저장합니다.

`.env`, `credentials/google_oauth_client.json`, `credentials/google_token.json` 원본 파일은 GitHub에 커밋하지 않습니다.

## 3. GitHub Actions 단독 테스트

GitHub 저장소의 Actions 메뉴에서 `Greating Instagram Data Collect`를 선택하고 `Run workflow`를 눌러 먼저 단독 실행합니다.

성공 기준:

```text
DAILY COLLECTION COMPLETED
```

까지 출력되고 Google Sheets의 당일 데이터가 update됩니다.

이 단독 테스트가 성공한 뒤 Apps Script 연결을 진행합니다.

## 4. Apps Script 생성

Google Apps Script 프로젝트에 `GithubDispatcher.gs` 내용을 추가합니다.

Project Settings의 Time zone은 반드시:

```text
Asia/Seoul
```

로 설정합니다.

## 5. Script Properties

Project Settings → Script Properties에 아래 값을 등록합니다.

```text
GITHUB_OWNER      = GitHub 사용자명 또는 Organization
GITHUB_REPO       = 저장소 이름
GITHUB_WORKFLOW   = instagram_daily_collect.yml
GITHUB_REF        = main
GITHUB_TOKEN      = GitHub Fine-grained PAT
WEBAPP_SECRET     = Streamlit ↔ Apps Script 호출용 임의의 긴 비밀문자열
```

`GITHUB_TOKEN`은 해당 repository에만 접근 가능한 Fine-grained PAT를 권장합니다. GitHub Actions workflow dispatch가 가능하도록 Actions 권한을 허용합니다.

## 6. Apps Script → GitHub 수동 테스트

Apps Script 편집기에서 아래 함수를 직접 실행합니다.

```javascript
runInstagramMorning()
```

GitHub Actions에 새 Run이 생기면 정상입니다.

## 7. 오전 / 오후 트리거 생성

Apps Script에서 아래 함수를 딱 한 번 실행합니다.

```javascript
setupInstagramTriggers()
```

생성되는 트리거:

```text
runInstagramMorning  → 08시대
runInstagramEvening  → 19시대
```

둘 다 동일한 전체 `daily_collect.py`를 실행합니다.

Apps Script 시간 기반 트리거 특성상 정확히 08:00:00 / 19:00:00을 보장하지는 않습니다.

## 8. Streamlit 수동 실행 버튼은 다음 단계

Apps Script를 Web App으로 배포한 뒤 Overview의 `지금 수집` 버튼이 `doPost()`를 호출하게 연결합니다.

Web App 연결 전에는 GitHub Actions 단독 실행과 Apps Script의 `runInstagramMorning()` 호출이 모두 성공하는지 먼저 확인합니다.
