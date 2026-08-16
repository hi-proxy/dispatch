# Dispatch 개발 핸드오프

기준일: 2026-08-16
상태: 로컬 실사용 가능한 SwiftUI 개발 빌드

제품 명세: [PRODUCT_SPEC.md](PRODUCT_SPEC.md)
저장소 상태: 로컬 Git repository, branch `main`. 구현 기준 SHA는 아래 착지 정보에 기록한다.

## Git 착지 정보

- 원격 저장소: 없음
- 기준 branch: `main`
- 구현 기준 commit: `1ae8c64` (`chore: drop the probe scripts now that the gate exists`)
- 런타임 DB, `.venv`, Swift 빌드 산출물, 로컬 권한 설정은 Git에서 제외

## 제품 경계

Dispatch는 이미 실행 중인 cmux 에이전트 터미널에 협업 기능을 붙였다 떼는 장비다.
에이전트 프로세스와 PTY를 소유하지 않으며 attach, detach, 앱 종료가 기존 터미널을
종료하지 않는다. 채팅 본문과 전달 상태의 SSOT는 Dispatch Server이고 터미널 호출은
본문 없이 inbox 존재만 알리는 고정 신호다.

```text
Global
├─ Projects
└─ Agents

Selected Project
├─ Chat
├─ Roles
├─ Shared
└─ Work
```

- 프로젝트 하나가 하나의 채팅방이다.
- Agents와 PM 프로필은 전역이다.
- 메시지, 역할, Shared, Work는 프로젝트별이다.
- 같은 세션은 한 프로젝트에서 하나의 역할만 맡는다.
- 같은 세션이 서로 다른 프로젝트 역할을 동시에 맡는 것은 허용한다.
- 역할은 세션 교체 뒤에도 유지되는 메시지 주소다.

## 현재 완료 범위

- cmux Codex·Claude 세션 자동 발견과 기존 터미널 무중단 attach/detach
- 에이전트 process TTY와 cmux surface의 유일 매핑 검증
- 서버 inbox, WebSocket 알림, received/processed ACK와 재연결 커서
- running/idle/needs_input gate와 고정 pager 호출
- SwiftUI 앱의 프로젝트 생성·선택·이름 변경
- 프로젝트별 로컬 Git 저장소 선택·검증과 branch/SHA 파싱 기준 연결
- 전역 Agents와 모든 프로젝트 역할 소속 표시
- 프로젝트별 역할 생성·편집·삭제·할당·교체·이력
- 미할당 역할 메시지 대기와 다음 담당 세션 전달
- 선택적 1회 온보딩 프롬프트
- PM 및 역할 아바타
- 여러 수신자와 역할 주소를 지원하는 카드형 Chat
- 입력창 위 한 줄의 역할 참여자 칩과 수신자 선택
- 선두 `@역할 @역할 본문`의 역할 우선 해석과 Enter 전송, 일반 Enter 줄바꿈
- 원문 보존형 메시지 Pretty 줄바꿈·`**형광펜**`과 메시지별 원문/Pretty 토글
- 프로젝트 SSOT 메시지 북마크
- 메시지 사이 구간 경계로 저장되는 Timeline Pin, 화면에 보이는 divider만 점등하는 인스펙터 Pins 탭, 메시지 seq 기반 과거 페이지 점프와 최신 복귀 버튼
- 짧은 `dispatch init` 호출문만 보내고 agent별 bootstrap API로 사용법·역할표를 읽는 Chat `Initialize`
- agent local name을 server principal ID로 변환하는 Reply/Request와 프로젝트 문맥 기억
- agent 공용 `history` 맥락 복원, 발신 저장 원문·track·tags echo, 무음절단 없는 20,000자 상한
- inbox stdout 단일 JSON, 사람 안내 stderr 분리, claim 누락 시 history 복구 규칙
- reply/request `--help`의 역할·track·tag·상속·프로젝트·저장 echo 예시
- reply/request 409의 `init` 선행 및 `history` 복구 안내
- PM confirm/direct/reference/ambient 알림 구분
- track, tags, reply context, 프로젝트 지정 Git의 실재 branch·commit만 허용하는 엄격 관심사 탐지·필터
- 폭 기반 태그 필터 `+` 펼치기와 여러 줄 `접기`
- Chat 최신 10건 즉시 표시, 이전 50건 백그라운드 병합, 상단 접근 시 50건 선로딩
- Shared key-value와 Work 보고·경과 시간
- 기존 `local` workspace를 기본 프로젝트로 승격하는 SQLite migration
- 채팅방 목록을 중심에 둔 사이드바. 프로젝트 아바타·저장소 branch·검색과 행
  context menu의 이름 변경·저장소 지정, 하단 agent 상태줄
- Pins·Roles·Shared·Work를 담는 우측 인스펙터와 시트로 여는 전역 Agents 화면
- 최신이 스크롤 원점이 되는 역순 타임라인. 과거를 앞에 붙여도 이미 배치된
  메시지를 다시 재지 않는다
- 방을 떠나도 최신 10건을 보관해 재진입 시 네트워크를 기다리지 않는 방별 캐시
- 프로젝트 전환 시 옛 스트림을 끊고 곧바로 새 방에 다시 붙는 재연결
- 방마다 1부터 세는 표시 번호. 저장과 정렬은 전역 seq를 쓰고 사람과 에이전트가
  부르는 번호만 방별로 보여준다
- 목록과 상세로 나눈 Agents 패널
- 새 메시지가 온 방에 점을 켜는 사이드바 표시
- 빈 프롬프트가 아닌 채 멈춘 세션을 표시하고 알리는 조작 대기 감지
- 권한 요청을 PM 앱에서 승인·거절하는 경로. 무엇을 요청하는지 도구와 입력을
  그대로 보여주며 터미널에는 아무것도 넣지 않는다 (아직 hook 등록 전)

## 실행

최초 설치:

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

앱 빌드와 실행:

```bash
DispatchMac/build-app.sh
open DispatchMac/build/Dispatch.app
```

앱은 `http://127.0.0.1:8790/health`를 확인하고 control daemon이 없으면 다음과 같은
구성으로 자동 시작한다.

```bash
.venv/bin/dispatch-node daemon --send
```

개발 포트:

- `127.0.0.1:8787`: Dispatch chat server
- `127.0.0.1:8790`: localhost control API

에이전트 터미널 연결은 앱의 글로벌 Agents 화면에서 수행한다. CLI 진단이 필요하면
`.venv/bin/dispatch-node ui` 또는 `.venv/bin/dispatch-node discover --diagnostic`을 쓴다.

## 검증

현재 착지 시점에 다음을 통과했다.

### 에이전트 신호와 화면 파싱

에이전트 도구가 세션 신호를 직접 주면 그것을 쓴다. 화면을 읽어 상태를 추론하는
규칙은 provider와 버전에 따라 조용히 깨지고, 깨졌다는 것을 아무도 모른다. 지금
`prompt_ready`가 강건한 이유는 "빈 프롬프트인가"만 보기 때문이며, 더 읽으려 할수록
약해진다.

이 저장소에서 확인한 것은 다음과 같다.

- 세션 발견: hook의 `session_id`·`cwd`·`transcript_path`
- 세션과 창의 연결: `ps`에 나오는 `--session-id`로 tty를 찾는다
- 무엇을 기다리는지: `PermissionRequest` hook이 도구 이름과 입력을 준다
- 에이전트에게 전하기: stop hook의 `hookSpecificOutput.additionalContext`.
  `decision: block`은 화면에 오류로 뜨고 `systemMessage`는 컨텍스트에 닿지 않는다

### UI 성능 원칙

성능 변경을 판정할 때는 비교 대상을 **같은 조건에서 다시 측정한다**. 예전에
적어둔 수치를 기준선으로 그대로 쓰면 정반대 결론이 나올 수 있다.

사용자 입력처럼 매 타이핑마다 변하는 고빈도 상태는 가장 작은 컴포넌트에 격리한다.
입력 한 번이 타임라인·목록·파싱·필터·네트워크 상태의 재계산이나 재렌더를 유발해서는
안 되며, 긴 입력과 누적된 긴 이력을 함께 둔 상태에서 검증한다. 기능 구현 전 상태 변경의
전파 범위를 확인하고 고빈도 경로에는 전체 화면 상태를 두지 않는다.

```bash
.venv/bin/pytest -q
# 82 passed

cd DispatchMac && swift test
# 10 passed

DispatchMac/build-app.sh
# production build complete, ad-hoc signed Dispatch.app
```

방 전환 성능은 메시지가 긴 방 재방문 기준 876ms에서 374ms로 줄었다. 타임라인을
역순으로 쌓아 과거를 앞에 붙여도 이미 배치된 행을 다시 재지 않게 한 결과다.
남은 374ms는 태그 트레이도 프리페치도 아니고 뷰 트리 구성 비용이다.

실행 중인 두 health endpoint도 `status: ok`를 반환했다. 실제 개발 DB에는 프로젝트
테이블과 `role_assignments.workspace_id`가 migration 되었으며 기존 역할·메시지 이력은
보존되었다.

## 주요 코드 위치

- `dispatch_server/db.py`: SQLite schema, migration, 프로젝트·역할·PM·메시지 SSOT
- `dispatch_server/app.py`: chat server HTTP/WebSocket API
- `dispatch_node/cmux.py`: cmux 발견, lifecycle, surface 검증
- `dispatch_node/supervisor.py`: watcher와 safe wake 수명 관리
- `dispatch_node/web.py`: SwiftUI용 localhost control API와 snapshot
- `dispatch_node/pm.py`: PM server client
- `DispatchMac/Sources/DispatchMac/AppModel.swift`: 선택 프로젝트와 앱 상태
- `DispatchMac/Sources/DispatchMac/ContentView.swift`: 채팅방 목록 사이드바와 Agents 시트
- `DispatchMac/Sources/DispatchMac/ChatView.swift`: 역순 타임라인, 수신자, 관심사 필터, 우측 인스펙터
- `DispatchMac/Sources/DispatchMac/RolesView.swift`: PM 카드와 역할 할당
- `DispatchMac/Sources/DispatchMac/AgentsView.swift`: 글로벌 세션과 프로젝트 소속

## 의도적으로 보류한 범위

- 프로젝트 삭제·archive lifecycle
- 인증과 권한 모델
- LAN 또는 인터넷 노출
- 두 번째 PC의 실제 운영 연결
- iTerm2와 Terminal.app adapter
- 토큰·비용의 신뢰 가능한 수집
- 앱 번들 내부 Python runtime과 LaunchAgent 패키징
- 장시간 soak 및 사람 입력 경쟁 조건 시험

현재 서버는 인증 없이 localhost만 신뢰하는 개발용이다. 인증과 TLS가 생기기 전에는
외부 인터페이스에 bind하지 않는다.

## 다음 작업 우선순위

제품 엔드스펙과 인수 조건은 [PRODUCT_SPEC.md](PRODUCT_SPEC.md)를 따른다. 다음 구조 작업은
아래 마일스톤 순서를 바꾸지 않는다.

1. M1 Server Extraction Ready: 설정·인증·membership·presence·backup
2. M2 실제 다중 클라이언트 LAN/VPN 검증과 soak
3. M3 Windows Node와 PowerShell/WSL terminal adapter
4. M4 Windows PM desktop client

실사용 중 발견한 UI 마찰은 불변조건을 깨지 않는 작은 변경으로 병행할 수 있다.
현재 열려 있는 것은 다음 셋이다.

- 사이드바 안읽음 배지와 마지막 메시지 미리보기. control API가 프로젝트별
  요약(`last_message_preview`·`last_at`·`unread_count`)을 주지 않아 미구현이다.
  UI 쪽은 행 구조가 이미 이를 받을 수 있다.
- 방 전환에 남은 374ms. 후보는 매 렌더마다 전체를 순회하는 `filteredTimeline`·
  `contexts`·`bookmarkedSequences`와 `MessagePrettyPrinter`의 재파싱이다.
- 터미널 어댑터 분리. cmux 의존이 `dispatch_node/cmux.py`에 모여 있으나 인터페이스로
  갈라져 있지는 않다. 경계를 그으면 일반 터미널 지원과 M3 Windows 어댑터 자리가
  같이 생기고, 파싱 규칙이 어댑터별 책임이 된다.
- 권한 승인을 켜는 일. 서버 재시작과 앱 재빌드, `PermissionRequest` hook 등록이
  필요하다. hook 등록은 사용자 설정을 건드리므로 범위를 정해야 한다.
- 빈 방 표시(`No messages`)는 프로젝트 삭제가 보류 범위라 실증하지 못했다.
  방향 의존을 코드에서 없애 두었으므로 새 프로젝트를 만들 일이 생기면 함께
  확인한다.

기존 터미널 독립성, 메시지 SSOT, running 상태 무입력 원칙은 이후 변경에서도 유지한다.
