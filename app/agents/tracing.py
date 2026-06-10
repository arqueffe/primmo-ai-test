from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.messages import BaseMessage

MAX_PREVIEW_ITEMS = 20
MAX_STRING_LEN = 2000
MAX_SERIALIZE_DEPTH = 4


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _truncate_text(value: str, max_len: int = MAX_STRING_LEN) -> str:
    if len(value) <= max_len:
        return value
    return f"{value[:max_len]}...<truncated>"


def _message_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return repr(content)

    parts: list[str] = []
    for part in content[:MAX_PREVIEW_ITEMS]:
        if isinstance(part, str):
            parts.append(part)
            continue
        if isinstance(part, dict) and part.get("type") == "text":
            parts.append(str(part.get("text", "")))
            continue
        parts.append(repr(part))
    return "\n".join(parts)


def _to_serializable(value: Any, depth: int = 0) -> Any:
    if depth >= MAX_SERIALIZE_DEPTH:
        return "<max_depth>"

    if value is None or isinstance(value, (bool, int, float, str)):
        if isinstance(value, str):
            return _truncate_text(value)
        return value

    if isinstance(value, BaseMessage):
        return {
            "type": value.type,
            "content": _truncate_text(_message_to_text(value.content)),
        }

    if isinstance(value, Exception):
        return {
            "type": value.__class__.__name__,
            "message": _truncate_text(str(value)),
        }

    if isinstance(value, dict):
        items = list(value.items())[:MAX_PREVIEW_ITEMS]
        return {
            str(k): _to_serializable(v, depth + 1)
            for k, v in items
        }

    if isinstance(value, (list, tuple, set)):
        items = list(value)[:MAX_PREVIEW_ITEMS]
        return [_to_serializable(item, depth + 1) for item in items]

    return _truncate_text(repr(value))


class AgentTraceRecorder(BaseCallbackHandler):
    """Records LangChain/LangGraph callback events and writes a JSON trace file."""

    def __init__(
        self,
        *,
        trace_dir: Path,
        query: str,
        dossier_id: str | None,
        model: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__()
        self._trace_id = uuid4().hex
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        self._trace_dir = trace_dir
        self._path = trace_dir / f"agent_trace_{timestamp}_{self._trace_id}.json"
        self._started_at = _utcnow_iso()
        self._events: list[dict[str, Any]] = []
        self._finalized = False
        self._metadata = {
            "trace_id": self._trace_id,
            "model": model,
            "dossier_id": dossier_id,
            "query": query,
            "extra": extra or {},
        }

        self.add_event(
            "trace_start",
            {
                "query": query,
                "dossier_id": dossier_id,
                "model": model,
            },
        )

    @property
    def file_path(self) -> Path:
        return self._path

    def add_event(self, event: str, payload: dict[str, Any] | None = None) -> None:
        self._events.append(
            {
                "timestamp": _utcnow_iso(),
                "event": event,
                "payload": _to_serializable(payload or {}),
            }
        )

    def on_chain_start(self, serialized: dict[str, Any], inputs: dict[str, Any], **kwargs: Any) -> Any:
        self.add_event(
            "chain_start",
            {
                "serialized": serialized,
                "inputs": inputs,
                "kwargs": kwargs,
            },
        )

    def on_chain_end(self, outputs: dict[str, Any], **kwargs: Any) -> Any:
        self.add_event(
            "chain_end",
            {
                "outputs": outputs,
                "kwargs": kwargs,
            },
        )

    def on_chain_error(self, error: BaseException, **kwargs: Any) -> Any:
        self.add_event(
            "chain_error",
            {
                "error": error,
                "kwargs": kwargs,
            },
        )

    def on_chat_model_start(self, serialized: dict[str, Any], messages: list[list[BaseMessage]], **kwargs: Any) -> Any:
        preview = []
        for batch in messages[:MAX_PREVIEW_ITEMS]:
            preview.append(
                [
                    {
                        "type": msg.type,
                        "content": _truncate_text(_message_to_text(msg.content)),
                    }
                    for msg in batch[:MAX_PREVIEW_ITEMS]
                ]
            )

        self.add_event(
            "chat_model_start",
            {
                "serialized": serialized,
                "messages": preview,
                "kwargs": kwargs,
            },
        )

    def on_llm_end(self, response: Any, **kwargs: Any) -> Any:
        self.add_event(
            "llm_end",
            {
                "response": response,
                "kwargs": kwargs,
            },
        )

    def on_llm_error(self, error: BaseException, **kwargs: Any) -> Any:
        self.add_event(
            "llm_error",
            {
                "error": error,
                "kwargs": kwargs,
            },
        )

    def on_tool_start(self, serialized: dict[str, Any], input_str: str, **kwargs: Any) -> Any:
        self.add_event(
            "tool_start",
            {
                "name": serialized.get("name") if isinstance(serialized, dict) else None,
                "serialized": serialized,
                "input": input_str,
                "kwargs": kwargs,
            },
        )

    def on_tool_end(self, output: Any, **kwargs: Any) -> Any:
        self.add_event(
            "tool_end",
            {
                "output": output,
                "kwargs": kwargs,
            },
        )

    def on_tool_error(self, error: BaseException, **kwargs: Any) -> Any:
        self.add_event(
            "tool_error",
            {
                "error": error,
                "kwargs": kwargs,
            },
        )

    def on_agent_action(self, action: Any, **kwargs: Any) -> Any:
        self.add_event(
            "agent_action",
            {
                "action": action,
                "kwargs": kwargs,
            },
        )

    def on_agent_finish(self, finish: Any, **kwargs: Any) -> Any:
        self.add_event(
            "agent_finish",
            {
                "finish": finish,
                "kwargs": kwargs,
            },
        )

    def finalize(
        self,
        *,
        answer: str | None = None,
        metrics: dict[str, Any] | None = None,
        error: BaseException | None = None,
    ) -> str:
        if self._finalized:
            return str(self._path)

        finished_at = _utcnow_iso()
        started_dt = datetime.fromisoformat(self._started_at)
        finished_dt = datetime.fromisoformat(finished_at)
        duration_ms = (finished_dt - started_dt).total_seconds() * 1000

        payload = {
            "trace_id": self._trace_id,
            "started_at": self._started_at,
            "finished_at": finished_at,
            "duration_ms": float(duration_ms),
            "metadata": _to_serializable(self._metadata),
            "events": self._events,
            "result": {
                "answer": _truncate_text(answer or ""),
                "metrics": _to_serializable(metrics or {}),
                "error": _to_serializable(error) if error is not None else None,
            },
        }

        self._trace_dir.mkdir(parents=True, exist_ok=True)
        with self._path.open("w", encoding="utf-8") as trace_file:
            json.dump(payload, trace_file, ensure_ascii=True, indent=2)

        self._finalized = True
        return str(self._path)
