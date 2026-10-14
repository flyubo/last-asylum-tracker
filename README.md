# Last Asylum Private Online Ranking Tracker

배포 가능한 비공개 랭킹 대시보드입니다. FastAPI, PostgreSQL, 일일 Render Cron Job, HTTP Basic 인증, CSV 내보내기와 30일 추이를 포함합니다.

## 수집 방식과 검증 상태

공개 랭킹 페이지 HTML을 읽습니다. 확인되지 않은 비공개/미문서화 API는 사용하지 않습니다.
- 글로벌 랭킹: https://lastasylum.gg/en/leaderboard/players/power
- 서버 149 예시: https://lastasylum.gg/en/leaderboard/servers/149

클라우드에서 자동 HTTP 요청이 허용되는지와 HTML 구조가 파서와 맞는지는 아직 검증되지 않았습니다. 첫 배포 후 대시보드에서 **지금 수집**을 눌러 확인하세요. 403/429가 발생하거나 구조가 바뀌면 우회하지 말고 접근 정책과 허용된 방법을 확인하세요.

## Render 배포
1. 이 비공개 GitHub 저장소를 Render에 연결합니다.
2. Render에서 **New → Blueprint**를 선택하고 저장소의 `render.yaml`을 적용합니다.
3. 생성될 웹 서비스, Cron 작업, PostgreSQL 데이터베이스와 요금을 검토합니다. 설정은 유료 플랜을 사용하므로 적용 전 현재 가격을 확인하세요.
4. 환경변수 `DASHBOARD_USERNAME`, `DASHBOARD_PASSWORD`를 설정합니다. 비밀번호는 코드나 GitHub에 저장하지 마세요.
5. 배포가 끝나면 웹 서비스의 `onrender.com` 주소를 열고 Basic Auth로 로그인합니다.
6. **지금 수집**을 눌러 데이터가 저장되는지 확인합니다.

## 자동 수집
`render.yaml`의 `0 23 * * *` UTC는 한국 시간으로 다음 날 오전 8시입니다. Cron 로그에서 성공 여부를 확인하세요.

## 보안 및 제한
- `/health`를 제외한 대시보드와 API는 HTTP Basic 인증을 요구합니다.
- 저장소는 비공개로 유지하고, 배포 URL과 로그인 정보를 공개하지 마세요.
- 웹 서비스 URL 자체는 인터넷에서 접근 가능하며 대시보드에 인증이 적용됩니다. 더 강한 네트워크 수준의 비공개가 필요하면 별도 접근 제어/VPN을 구성해야 합니다.
- Render의 로컬 파일시스템은 영구 저장소가 아니므로 PostgreSQL을 사용합니다.
- 플레이어 식별은 이름과 길드 태그 조합입니다. 변경 시 별개 플레이어처럼 보일 수 있습니다.
- 최초 수집 전의 과거 기록은 복원하지 않습니다. 사이트의 이용약관과 요청 제한을 준수하세요.

## 서버 변경
대시보드에서 서버 ID를 입력하면 수동 수집할 수 있습니다. 일일 Cron은 `render.yaml`의 `python worker.py --server 149`에 설정된 서버만 수집합니다.

## 로컬 테스트
Python 3.10+ 및 PostgreSQL이 필요합니다.
```bash
pip install -r requirements.txt
# DATABASE_URL, DASHBOARD_USERNAME, DASHBOARD_PASSWORD 환경변수를 설정
uvicorn app:app --reload
```
