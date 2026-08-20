#!/bin/sh
# Fungis hook.
#
# cmux 없이 에이전트 세션을 발견하고 메시지를 전한다. 표준 hook 이벤트만
# 쓰므로 cmux와 공존하고 cmux가 없는 환경에서도 동작한다.
#
# 전달은 hookSpecificOutput.additionalContext로 한다. decision block도 컨텍스트에
# 닿지만 화면에 "Stop hook blocking error"로 떠서 오류처럼 보인다. systemMessage는
# 조용하지만 컨텍스트에 닿지 않는다. 셋 다 시험해 확인했다.
#
# 터미널에는 아무것도 넣지 않는다. 그래서 입력 안전성(명세 3.4)이 걸리는
# 지점이 없다. 전달은 읽기만 하고 타임라인에 아무것도 남기지 않는다.
set -u
event="${1:-unknown}"
repo="$(cd "$(dirname "$0")/../.." && pwd)"
store="${FUNGIS_HOOK_STORE:-$HOME/.fungis}"
mkdir -p "$store" 2>/dev/null || true

payload="$(cat 2>/dev/null || true)"

FUNGIS_REPO="$repo" FUNGIS_STORE="$store" FUNGIS_EVENT="$event" \
  python3 - "$payload" <<'PY' 2>/dev/null || echo '{}'
import json, os, subprocess, sys

event = os.environ.get("FUNGIS_EVENT", "unknown")
repo = os.environ.get("FUNGIS_REPO", ".")
store = os.environ.get("FUNGIS_STORE", ".")
try:
    payload = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
except Exception:
    payload = {}

# 세션 장부. cmux의 hook-sessions.json이 하던 일이다. tty는 여기서 넣지
# 않는다. hook payload에 pid가 없어서, 창을 찾을 때 session_id로 ps를 뒤진다.
if event == "session-start" and payload.get("session_id"):
    path = os.path.join(store, "sessions.json")
    try:
        with open(path) as fh:
            sessions = json.load(fh)
    except Exception:
        sessions = {}
    sessions[payload["session_id"]] = {
        "session_id": payload["session_id"],
        "cwd": payload.get("cwd"),
        "transcript_path": payload.get("transcript_path"),
        "source": payload.get("source"),
    }
    with open(path, "w") as fh:
        json.dump(sessions, fh, ensure_ascii=False, indent=2)

if event != "stop":
    print("{}")
    raise SystemExit

cli = os.path.join(repo, ".venv", "bin", "fungis")
if not os.access(cli, os.X_OK):
    print("{}")
    raise SystemExit

try:
    done = subprocess.run(
        [cli, "inbox"], cwd=repo, capture_output=True, text=True, timeout=20
    )
    data = json.loads(done.stdout.strip().splitlines()[-1])
    messages = data.get("messages") or []
except Exception:
    messages = []

if not messages:
    print("{}")
    raise SystemExit

# 참조 표시를 지우지 않는다. inbox의 for_me를 여기서 버리면 규범이
# "for_me=false면 답하지 않는다"라고 해도 근거가 사라진다. 남에게 온 말에
# 답하게 되는 자리다.
mine = [m for m in messages if m.get("for_me", True) and not m.get("later")]
copied = [m for m in messages if not m.get("for_me", True)]
deferred = [m for m in messages if m.get("later")]
head = "[fungis] 새 메시지 %d건" % len(messages)
if mine:
    head += ". 답은 fungis reply로 보낸다."
elif deferred and not copied:
    head += ". 전부 [나중] 이다 — 하던 걸음을 마치고 본다."
else:
    head += ". 전부 참조다 — 맥락으로만 두고 답하지 않는다."
lines = [head]
for m in messages:
    if m.get("later"):
        mark = " [나중]"
    elif not m.get("for_me", True):
        mark = " [참조]"
    else:
        mark = ""
    lines.append(
        "#%s %s%s: %s"
        % (m.get("seq"), m.get("from"), mark, (m.get("body") or "").strip())
    )
if mine and copied:
    lines.append("[참조] 표시는 남에게 온 말이다. 답하지 않는다.")
if deferred:
    lines.append(
        "[나중] 은 보낸 쪽이 깨우지 않고 둔 말이다. 하던 걸음을 마치고 본다 — "
        "이번 턴에 답하지 않는다."
    )

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "Stop",
        "additionalContext": "\n\n".join(lines),
    }
}, ensure_ascii=False))
PY
