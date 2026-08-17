# Fungis

이미 돌고 있는 cmux 에이전트 터미널들을 한 채팅방에 불러 앉히는 macOS 앱.
재시작하지 않고 붙였다 뗀다.

담당자는 세션이 아니라 역할이다. 세션을 갈아끼워도 대화와 대기 중인 메시지는
그 역할에 남는다.

## 구조

```
SwiftUI 앱 ──▶ Node ──▶ Server
              :8790     :8787
                │
                ▼
          기존 터미널 (cmux)
```

- **Server** — 메시지·역할·프로젝트의 SSOT. 터미널을 모른다
- **Node** — 이 PC의 터미널 발견과 binding, 안전 호출, 로컬 Git 매핑
- **앱** — localhost control API에만 연결한다

호출은 새 메시지가 있다는 사실만 터미널에 알리고, 본문은 에이전트가 서버에서
조회한다.

## 실행

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/fungis-node install-agent-cli

FungisMac/build-app.sh
open FungisMac/build/Fungis.app
```

`install-agent-cli`는 `~/.local/bin/fungis`를 놓는다. 에이전트가 터미널에서
쓰는 명령이라 이게 없으면 배정을 받아도 아무것도 못 한다.

앱이 control daemon을 확인하고 없으면 직접 띄운다. 최초 빌드 뒤에는 앱만 열면
된다.

## 화면

- **사이드바** — 프로젝트가 곧 채팅방. 우클릭으로 이름 변경과 Git 저장소 지정
- **채팅** — 역할 칩으로 수신자 선택, `@역할 본문` 뒤 Enter로 전송.
  `**형광펜**` 같은 표식은 원문을 보존한 채 화면에서만 변환된다
- **인스펙터** — Pins · Roles · Shared · Work
- **상태줄** — 클릭하면 전역 Agents 화면

## 에이전트 쪽

역할을 배정받은 에이전트는 짧은 호출문 하나만 받는다.

```
fungis init --project <id>
```

사용법과 역할표는 그 뒤 bootstrap API에서 읽는다. 이후 `fungis inbox`로
받고 `fungis reply`로 답한다.

## 개발

```bash
.venv/bin/pytest -q
cd FungisMac && swift test
```

- `fungis_server/` — SQLite schema, HTTP/WebSocket API
- `fungis_node/` — cmux 발견, lifecycle, control API
- `FungisMac/` — SwiftUI 앱

## 문서

- [제품 계약과 마일스톤](docs/PRODUCT_SPEC.md)
- [현재 착지 상태와 재시작 절차](docs/HANDOFF.md)

## 범위

인증 없이 localhost만 신뢰하는 개발용이다. 인증과 TLS가 생기기 전에는 외부
인터페이스에 bind하지 않는다.
