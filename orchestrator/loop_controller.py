"""Loop controller to orchestrate DRAFT/REVIEW iterations.

The module keeps ``loop_state.json`` in metadata/<SID>/ and appends Reflexion
records to ``rag/memories/reflexion_store.jsonl`` whenever a blocking failure
occurs, as required by TODO 14.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from common.logging import get_logger
from common.paths import ensure_dir, get_metadata_dir
from rag.memories import ReflexionRecord, append_memory

LOGGER = get_logger(__name__)


def _default_state(sid: str, max_loops: int) -> Dict[str, Any]:
    return {
        "sid": sid,
        "max_loops": max_loops,
        "current_loop": 0,
        "history": [],
        "last_result": None,
    }


@dataclass
class LoopOutcome:
    loop: int
    success: bool
    stage: str
    reason: str
    blocking: bool
    fix_hint: str
    timestamp: str


class LoopController:
    """Manage iterative loops for a Scenario ID."""

    def __init__(self, sid: str, max_loops: int = 3) -> None:
        self.sid = sid
        metadata_dir = ensure_dir(get_metadata_dir(sid))
        self.state_path = metadata_dir / "loop_state.json"
        self.state = self._load_state(max_loops)

    def _load_state(self, max_loops: int) -> Dict[str, Any]:
        if self.state_path.exists():
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        state = _default_state(self.sid, max_loops)
        self._write_state(state)
        return state

    @property
    def current_loop(self) -> int:
        return int(self.state.get("current_loop", 0))

    @property
    def max_loops(self) -> int:
        return int(self.state.get("max_loops", 1))

    def start_loop(self) -> int:
        """Increment the loop counter and persist the state."""

        if self.current_loop >= self.max_loops:
            raise RuntimeError(f"Loop limit reached ({self.max_loops}) for {self.sid}")
        self.state["current_loop"] = self.current_loop + 1
        self._write_state(self.state)
        LOGGER.info("Loop %s/%s started for %s", self.current_loop, self.max_loops, self.sid)
        return self.current_loop

    def record_success(self, stage: str, note: str = "") -> LoopOutcome:
        outcome = self._record_outcome(success=True, stage=stage, reason=note)
        return outcome

    def record_failure(
        self,
        stage: str,
        reason: str,
        fix_hint: str = "",
        blocking: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> LoopOutcome:
        outcome = self._record_outcome(
            success=False,
            stage=stage,
            reason=reason,
            fix_hint=fix_hint,
            blocking=blocking,
            metadata=metadata,
        )
        append_memory(
            ReflexionRecord(
                sid=self.sid,
                loop_count=outcome.loop,
                stage=stage,
                reason=reason,
                remediation_hint=fix_hint,
                blocking=blocking,
                metadata=(metadata or {}),
                timestamp=outcome.timestamp,
            )
        )
        return outcome

    def _record_outcome(
        self,
        *,
        success: bool,
        stage: str,
        reason: str,
        fix_hint: str = "",
        blocking: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> LoopOutcome:
        if self.current_loop == 0:
            raise RuntimeError("Call start_loop() before recording an outcome")
        timestamp = datetime.now(timezone.utc).isoformat()
        entry = {
            "loop": self.current_loop,
            "stage": stage,
            "success": success,
            "blocking": blocking,
            "reason": reason,
            "fix_hint": fix_hint,
            "timestamp": timestamp,
            "metadata": metadata or {},
        }
        history = self.state.setdefault("history", [])
        history.append(entry)
        self.state["last_result"] = "success" if success else "failure"
        self._write_state(self.state)
        return LoopOutcome(
            loop=self.current_loop,
            success=success,
            stage=stage,
            reason=reason,
            blocking=blocking,
            fix_hint=fix_hint,
            timestamp=timestamp,
        )

    def should_continue(self) -> bool:
        """Return True when another loop is allowed."""

        if self.current_loop < self.max_loops and self.state.get("last_result") == "failure":
            return True
        if self.current_loop == 0:
            return True
        return False

    def _write_state(self, state: Dict[str, Any]) -> None:
        self.state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Loop controller utility")
    parser.add_argument("--sid", required=True)
    parser.add_argument(
        "--action",
        choices=["start", "success", "failure", "status"],
        required=True,
    )
    parser.add_argument("--stage", default="REVIEW")
    parser.add_argument("--reason", default="")
    parser.add_argument("--fix-hint", default="")
    parser.add_argument("--note", default="")
    parser.add_argument("--blocking", action="store_true")
    parser.add_argument("--max-loops", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    controller = LoopController(args.sid, max_loops=args.max_loops)

    if args.action == "start":
        loop = controller.start_loop()
        LOGGER.info("Loop %s started", loop)
        return
    if args.action == "success":
        controller.record_success(stage=args.stage, note=args.note or args.reason)
        LOGGER.info("Loop %s recorded success", controller.current_loop)
        return
    if args.action == "failure":
        controller.record_failure(
            stage=args.stage,
            reason=args.reason or "unspecified",
            fix_hint=args.fix_hint,
            blocking=args.blocking,
        )
        LOGGER.info("Loop %s recorded failure", controller.current_loop)
        return
    if args.action == "status":
        LOGGER.info(
            "SID %s loop status: %s/%s loops, last result=%s",
            controller.sid,
            controller.current_loop,
            controller.max_loops,
            controller.state.get("last_result"),
        )


if __name__ == "__main__":
    main()
