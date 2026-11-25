# LA Tracker — Claude 개발 인수인계

> 이 문서는 `la-api-platform` 브랜치의 API 플랫폼 작업 인수인계입니다. 기존 서버 139 랭킹 트래커와 기본 브랜치는 별도이며 수정하지 않습니다.

## 최종 목표

Last Asylum의 약 2,000개 게임 API를 활용해 사용자가 원하는 게임 정보를 검색하고 조회할 수 있는 개인용 웹사이트를 만드는 프로젝트입니다.

서버 139 영웅 랭킹만 추적하는 프로젝트가 아닙니다. TOK, JOKA, HUG 조회는 API 탐색의 초기 사례일 뿐이며, 핵심은 API 카탈로그를 기반으로 다양한 데이터를 검색·조회하는 범용 개인 도구입니다.

## 저장소 및 브랜치

- 코드 저장소: `flyubo/last-asylum-tracker`
- 작업 브랜치: `la-api-platform`
- 캡처 저장소: `flyubo/la-tracker-captures` (비공개)
- 기존 기본 브랜치 및 서버 139 대시보드는 건드리지 말 것.

## 현재 코드 구성

- `la_api/pcap_session.py`: PCAP 파싱, TCP stream 재조립, 프레임 해석, 캡처에서 로그인/재접속 세션 정보 추출
- `la_api/socket_client.py`: 게임 서버 TCP 연결, 로그인/재접속 프레임 처리, API 요청 및 응답 처리
- `la_api/local_server.py`: 로컬 HTTP 서버 (`127.0.0.1:8765`)
- `la_api/local_console.html`: 브라우저 콘솔 UI
- `la_api/api_catalog.json`: API 카탈로그
- `run_la_tracker.py`: 로컬 실행 진입점

현재 로컬 HTTP 경로:
- `/api/session/import`
- `/api/session/connect`
- `/api/query/rank`
- `/api/query/union`
- `/api/session/disconnect`
- `/api/status`
- `/api/catalog`

## PCAP에서 확인된 사실

2026-11-21 캡처 `PCAPdroid_25_11월_21_15_07.pcap`은 비공개 저장소 `flyubo/la-tracker-captures`에 있습니다. 분석 과정에서 6,146개 패킷, 476개 프레임, 156개 메시지 종류를 확인했습니다.

두 번째 TCP 연결에서 실제 게임 클라이언트가 보낸 재접속 흐름이 관찰됐습니다.

클라이언트 방향:
1. `LoginNoticeC2S`
2. `LoginReconnectC2S` (body 117 bytes)
3. `GetUnionHelpListC2S`
4. `LoginSuccessC2S`

서버 방향:
1. `LoginNoticeS2C`
2. `AckCode` (body 16 bytes)
3. `AckCode` (body 19 bytes)
4. `LoginReconnectTokenKeyS2C`
5. `EyGameLoginReconnectRespS2C`
6. `EyGameMiddleAgesReconnectRespS2C`

주의: 위 목록은 각 TCP 방향의 stream 순서입니다. 전체 송수신 교차 시간순으로 단정하지 마세요. 최초 PCAP에는 재접속 요청이 없었고, 11월 21일 캡처에서 실제 `LoginReconnectC2S`가 처음 확인됐습니다.

## 최근 반영 사항

- `pcap_session.py`에서 캡처 안의 실제 `LoginReconnectC2S` 본문을 추출해 세션 객체에 보관하도록 변경했습니다.
- `socket_client.py`에서 해당 캡처된 재접속 요청 프레임을 사용하는 경로를 반영했습니다.
- 코드 변경 후 기존 LA API core tests GitHub Actions는 성공했습니다.
- 캡처 저장소의 분석 workflow에도 재접속 본문 추출 검증 단계를 추가했습니다.
- **중요: 실제 서버 재접속 및 실제 API 조회 성공은 아직 검증되지 않았습니다.** 테스트 통과를 서버 접속 성공으로 표현하지 마세요.
- Windows 실행 파일 빌드 workflow는 사용자가 원하지 않아 제거했습니다. 소스 코드 중심으로 유지합니다.

## 다음 우선 작업

1. `pcap_session.py`의 세션 추출 필드와 실제 PCAP protobuf 구조를 검증합니다. 특히 재접속 요청 body를 어떤 방식으로 보관·사용하는지, 토큰/계정 값의 출처와 만료 가능성을 점검합니다.
2. `socket_client.py`의 프레임 카운터, 암호화/복호화, ACK 순서, 재접속 응답 파싱이 실제 캡처와 일치하는지 확인합니다. 확인되지 않은 counter reset이나 응답 필드 번호를 추측으로 확정하지 마세요.
3. 실제 사용자 본인의 새 세션으로 연결을 시험하고, 성공 여부를 단계별로 기록합니다. 캡처된 인증 자료를 제3자 계정에 사용하거나 인증을 우회하는 기능은 만들지 마세요.
4. 연결 성공 후 API catalog와 protobuf schema를 체계화하고, 사용자가 API를 검색·선택·호출할 수 있는 범용 탐색 UI를 구현합니다.
5. 기존 테스트를 확장해 프레임 파싱, 암복호화, ACK 시퀀스, 응답 protobuf 파싱, 오류 처리 등을 회귀 검증합니다.

## 보안 및 협업 주의사항

- PCAP에는 계정 식별자, 재접속 토큰 등 민감 정보가 포함될 수 있습니다. 비공개 캡처 저장소를 공개하지 마세요.
- 로그, Actions artifact, 문서, 커밋 메시지에 토큰 원문이나 계정 인증 데이터를 출력하지 마세요.
- 필요하면 필드 번호, wire type, 길이만 기록하고 실제 값은 마스킹합니다.
- 사용자는 Claude에게 이 저장소를 넘겨 UI와 전체 플랫폼 개발을 이어갈 예정입니다. 목적은 단순한 서버 139 트래커 확장이 아니라, API를 자유롭게 검색하고 필요한 정보를 얻는 개인용 LA Tracker입니다.
