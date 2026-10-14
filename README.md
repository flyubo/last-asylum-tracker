# Last Asylum 랭킹 트래커

LastAsylum.gg의 공개 서버 랭킹 페이지를 하루 한 번 읽어 일별 스냅샷을 저장하는 개인용 트래커입니다.

## GitHub 무료 자동 수집

- 워크플로: `.github/workflows/daily-collect.yml`
- 실행 시간: 매일 UTC 23:00 = 한국 시간 다음 날 오전 08:00
- 기본 서버: 139
- 저장 위치: `data/snapshots.json`
- 수동 실행: GitHub 저장소의 **Actions → Daily Last Asylum ranking collection → Run workflow**
- 기록은 최대 365회까지 유지합니다.

이 구성은 상시 서버 없이 GitHub Actions로 수집하고 JSON 기록을 저장합니다. 비공개 저장소의 Actions 실행은 GitHub Free 월간 무료 사용량에 포함되며, 계정의 사용량 한도를 넘으면 추가 요금 또는 실행 제한이 생길 수 있습니다. 실행 시간을 짧게 유지하고 Billing의 Actions 사용량을 확인하세요.

## 대시보드

`index.html`은 정적 대시보드입니다. GitHub Pages로 게시하면 브라우저에서 검색·정렬·추이 확인이 가능합니다. 다만 GitHub Free에서는 Pages 공개 범위가 저장소 공개 설정에 따라 달라질 수 있습니다. 저장소를 공개로 바꾸면 소스 코드와 `data/snapshots.json`의 기록도 누구나 볼 수 있으므로, **사용자 동의 없이 저장소를 공개로 전환하지 마세요.**

현재 저장소가 비공개라면:
1. Actions 탭에서 워크플로가 활성화되어 있는지 확인합니다.
2. **Actions → Daily Last Asylum ranking collection → Run workflow**로 최초 수집을 시험합니다.
3. 성공 후 `data/snapshots.json`에 데이터가 기록되었는지 확인합니다.
4. 대시보드를 온라인에 게시하려면 저장소 공개 전환에 동의하거나, Pages가 비공개 저장소를 지원하는 유료 플랜을 이용해야 할 수 있습니다.

## 수집 출처 및 제한

- 서버 139: https://lastasylum.gg/en/leaderboard/servers/139
- 공개 HTML을 읽습니다. 비공개 또는 미문서화 API를 사용하지 않습니다.
- 사이트의 HTML 구조 변경이나 자동 요청 차단으로 수집이 실패할 수 있습니다.
- HTTP 403/429가 발생하면 접근 정책과 허용된 방법을 확인하고 우회하지 마세요.
- 플레이어 식별은 이름과 길드 태그 기준이며, 이름/태그가 바뀌면 다른 플레이어처럼 표시될 수 있습니다.
- 과거 데이터는 최초 수집 시점부터 쌓입니다.

## 서버 변경

다른 서버를 자동 수집하려면 `.github/workflows/daily-collect.yml` 안의 다음 명령을 변경하세요.

```yaml
run: python scripts/github_collect.py --server 139
```

`index.html`은 선택한 서버의 기록을 `data/snapshots.json`에서 읽습니다. 서버 ID는 워크플로에 추가로 수집되도록 설정해야 기록이 생깁니다.

## 기존 Render 구성

`app.py`, `worker.py`, `render.yaml`은 기존 FastAPI/PostgreSQL 배포용으로 남겨두었습니다. GitHub Actions 기반 무료 구성에는 필요하지 않습니다.
