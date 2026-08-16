from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Callable

from .cmux import CmuxAdapter
from .registry import LocalRegistry


@dataclass(frozen=True)
class GateDecision:
    recipient_id: str
    eligible: bool
    reason: str
    lifecycle: str
    pending_count: int
    through_seq: int
    settle_remaining_seconds: float
    would_send: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


class IdleGate:
    def __init__(
        self,
        registry: LocalRegistry,
        adapter: CmuxAdapter,
        *,
        settle_seconds: float = 5.0,
        now: Callable[[], datetime] | None = None,
        wake_text: str = "[dispatch] inbox",
    ) -> None:
        self.registry = registry
        self.adapter = adapter
        self.settle_seconds = settle_seconds
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.wake_text = wake_text

    def refresh(self, recipient_id: str) -> dict:
        binding = self.registry.binding(recipient_id)
        if binding is None:
            raise LookupError(f"active binding not found: {recipient_id}")
        candidate = self.adapter.resolve_binding_candidate(
            provider=binding["provider"],
            agent_session_id=binding["agent_session_id"],
            surface_id=binding["surface_id"],
        )
        if candidate is None:
            raise LookupError(
                f"binding target is not uniquely discoverable: {recipient_id}"
            )
        if not candidate.binding_verified:
            raise LookupError(
                "binding target failed PID/TTY verification: "
                f"{candidate.verification_reason}"
            )
        return self.registry.refresh_candidate(recipient_id, candidate)

    def evaluate(self, recipient_id: str, *, refresh: bool = True) -> GateDecision:
        if refresh:
            self.refresh(recipient_id)
        binding = self.registry.binding(recipient_id)
        if binding is None:
            raise LookupError(f"active binding not found: {recipient_id}")
        pending = self.registry.pending_summary(recipient_id)
        lifecycle = binding["lifecycle"]
        elapsed = self._elapsed_seconds(binding["lifecycle_changed_at"])
        remaining = max(0.0, self.settle_seconds - elapsed)
        common = dict(
            recipient_id=recipient_id,
            lifecycle=lifecycle,
            pending_count=pending["pending_count"],
            through_seq=pending["through_seq"],
            settle_remaining_seconds=round(remaining, 3),
        )
        if pending["pending_count"] == 0:
            return GateDecision(eligible=False, reason="no_pending", **common)
        # idle만 믿고 나머지는 전부 화면이 판단한다. 한 턴도 안 돈 새 세션의
        # lifecycle은 믿을 수 없다 — cmux가 unknown으로 적기도 하고 running에
        # 머물기도 한다(8/16 tester1은 unknown, tester2는 running이었고 둘 다
        # 화면은 빈 프롬프트였다). lifecycle만 보면 갓 배정한 에이전트는 첫
        # 메시지를 영원히 못 받고, 사람이 터미널을 건드려 줘야만 풀린다.
        #
        # 화면으로 내려도 안전하다. 진짜로 일하는 중이면 빈 프롬프트가 없어서
        # 어차피 못 깨운다. 여기까지 왔다는 건 보낼 것이 있다는 뜻이라
        # read-screen 호출도 대기 중일 때만 일어난다.
        if lifecycle != "idle" and not self.adapter.prompt_ready(
            binding["surface_id"]
        ):
            return GateDecision(
                eligible=False, reason=f"lifecycle_{lifecycle}", **common
            )
        if remaining > 0:
            return GateDecision(eligible=False, reason="settling", **common)
        if self.registry.outstanding_wake(recipient_id) is not None:
            return GateDecision(
                eligible=False, reason="wake_unconfirmed", **common
            )
        return GateDecision(
            eligible=True,
            reason="eligible",
            would_send=self.wake_text,
            **common,
        )

    def run(
        self, recipient_id: str, *, send: bool = False, refresh: bool = True
    ) -> GateDecision:
        decision = self.evaluate(recipient_id, refresh=refresh)
        if send and decision.eligible:
            binding = self.registry.binding(recipient_id)
            assert binding is not None
            self.adapter.wake(binding["surface_id"], decision.would_send or "")
            self.registry.record_wake(recipient_id, decision.through_seq)
        return decision

    def _elapsed_seconds(self, timestamp: str) -> float:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        return max(0.0, (self.now() - parsed).total_seconds())
