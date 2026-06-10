from datetime import datetime, timezone
from math import ceil
import json
from pathlib import Path


class MetricsStore:
    MODEL_PRICING_PER_1M = {
        "openai/gpt-4o": (2.5, 10.0),
        "gpt-4o": (2.5, 10.0),
        "gpt-5.4-mini": (0.75, 4.5),
    }

    def __init__(self, state_file: str | Path | None = None):
        self._sequence = 0
        self._query_history: list[dict] = []
        self._operation_history: list[dict] = []
        self._state_file = Path(state_file) if state_file else None

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _next_id(self) -> int:
        self._sequence += 1
        return self._sequence

    @staticmethod
    def _has_model(model: str | None) -> bool:
        return bool(model and str(model).strip())

    @staticmethod
    def _normalize_token_usage(token_usage: dict | None) -> tuple[int, int, int]:
        usage = token_usage or {}
        prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
        completion_tokens = int(usage.get("completion_tokens", 0) or 0)
        total_tokens = int(usage.get("total_tokens", prompt_tokens + completion_tokens) or 0)

        # DSPy/KGGen usage can provide only total_tokens; treat it as input tokens
        # for cost estimation when split details are unavailable.
        if prompt_tokens == 0 and completion_tokens == 0 and total_tokens > 0:
            prompt_tokens = total_tokens

        return prompt_tokens, completion_tokens, total_tokens

    @classmethod
    def estimate_cost_usd(
        cls,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> float:
        rates = cls.MODEL_PRICING_PER_1M.get(model)
        if rates is None and model.startswith("openai/"):
            rates = cls.MODEL_PRICING_PER_1M.get(model.replace("openai/", ""))
        if rates is None:
            return 0.0
        input_rate, output_rate = rates
        return (prompt_tokens * input_rate + completion_tokens * output_rate) / 1_000_000

    @staticmethod
    def _p95(values: list[float]) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        idx = max(0, ceil(0.95 * len(ordered)) - 1)
        return float(ordered[idx])

    def record_operation(
        self,
        *,
        name: str,
        category: str,
        latency_ms: float,
        token_usage: dict | None = None,
        model: str | None = None,
        metadata: dict | None = None,
        persist: bool = True,
    ) -> dict | None:
        if not self._has_model(model):
            return None

        prompt_tokens, completion_tokens, total_tokens = self._normalize_token_usage(
            token_usage
        )
        cost_usd = (
            self.estimate_cost_usd(model, prompt_tokens, completion_tokens)
            if model
            else 0.0
        )

        record = {
            "id": self._next_id(),
            "ts": self._now_iso(),
            "name": name,
            "category": category,
            "latency_ms": float(latency_ms),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cost_usd": float(cost_usd),
            "model": model,
            "metadata": metadata or {},
        }
        self._operation_history.append(record)
        if persist:
            self.save_state()
        return record

    def record_query_execution(
        self,
        *,
        question: str,
        dossier_id: str | None,
        strategy: str,
        model: str,
        metrics: dict,
    ) -> dict:
        prompt_tokens, completion_tokens, total_tokens = self._normalize_token_usage(
            {
                "prompt_tokens": metrics.get("prompt_tokens", 0),
                "completion_tokens": metrics.get("completion_tokens", 0),
                "total_tokens": metrics.get("total_tokens", 0),
            }
        )

        cost_usd = float(
            metrics.get(
                "cost_usd",
                self.estimate_cost_usd(model, prompt_tokens, completion_tokens),
            )
        )

        record = {
            "id": self._next_id(),
            "ts": self._now_iso(),
            "question": question,
            "dossier_id": dossier_id,
            "strategy": strategy,
            "latency_ms": float(metrics.get("latency_ms", 0.0) or 0.0),
            "retrieval_latency_ms": float(
                metrics.get("retrieval_latency_ms", 0.0) or 0.0
            ),
            "chat_latency_ms": float(metrics.get("chat_latency_ms", 0.0) or 0.0),
            "embedding_latency_ms": float(
                metrics.get("embedding_latency_ms", 0.0) or 0.0
            ),
            "graph_prepare_latency_ms": float(
                metrics.get("graph_prepare_latency_ms", 0.0) or 0.0
            ),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cost_usd": cost_usd,
            "retrieved_nodes": int(metrics.get("retrieved_nodes", 0) or 0),
            "context_statements": int(metrics.get("context_statements", 0) or 0),
        }
        self._query_history.append(record)

        self.record_operation(
            name="graph_prepare",
            category="query",
            latency_ms=record["graph_prepare_latency_ms"],
            metadata={"question": question, "dossier_id": dossier_id},
            model=model,
            persist=False,
        )
        self.record_operation(
            name="embedding",
            category="query",
            latency_ms=record["embedding_latency_ms"],
            metadata={"question": question, "dossier_id": dossier_id},
            model=model,
            persist=False,
        )
        self.record_operation(
            name="retrieval",
            category="query",
            latency_ms=record["retrieval_latency_ms"],
            metadata={
                "question": question,
                "dossier_id": dossier_id,
                "retrieved_nodes": record["retrieved_nodes"],
                "context_statements": record["context_statements"],
            },
            model=model,
            persist=False,
        )
        self.record_operation(
            name="chat",
            category="query",
            latency_ms=record["chat_latency_ms"],
            token_usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            },
            model=model,
            metadata={"question": question, "dossier_id": dossier_id},
            persist=False,
        )
        self.record_operation(
            name="query_total",
            category="query",
            latency_ms=record["latency_ms"],
            token_usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            },
            model=model,
            metadata={"question": question, "dossier_id": dossier_id},
            persist=False,
        )

        self.save_state()

        return record

    def summary(self) -> dict:
        latencies = [float(item.get("latency_ms", 0.0) or 0.0) for item in self._query_history]
        total_queries = len(self._query_history)
        avg_latency = sum(latencies) / total_queries if total_queries else 0.0
        total_cost = sum(
            float(item.get("cost_usd", 0.0) or 0.0) for item in self._query_history
        )

        relevant_operations = [
            item for item in self._operation_history if self._has_model(item.get("model"))
        ]

        operation_latencies_by_name: dict[str, list[float]] = {}
        operation_cost_by_name: dict[str, float] = {}
        for item in relevant_operations:
            name = str(item.get("name", "unknown"))
            operation_latencies_by_name.setdefault(name, []).append(
                float(item.get("latency_ms", 0.0) or 0.0)
            )
            operation_cost_by_name[name] = operation_cost_by_name.get(name, 0.0) + float(
                item.get("cost_usd", 0.0) or 0.0
            )

        operation_avg_latency_ms = {
            name: (sum(values) / len(values)) if values else 0.0
            for name, values in operation_latencies_by_name.items()
        }

        judge_operations = [
            item for item in relevant_operations if str(item.get("name", "")) == "kg_judge"
        ]
        judge_latencies = [
            float(item.get("latency_ms", 0.0) or 0.0) for item in judge_operations
        ]
        judge_total_cost = sum(
            float(item.get("cost_usd", 0.0) or 0.0) for item in judge_operations
        )

        return {
            "total_queries": total_queries,
            "avg_latency_ms": float(avg_latency),
            "p95_latency_ms": self._p95(latencies),
            "total_cost_usd": float(total_cost),
            "avg_relevance_score": None,
            "operation_count": len(relevant_operations),
            "operation_avg_latency_ms": operation_avg_latency_ms,
            "operation_total_cost_usd": operation_cost_by_name,
            "judge_review_count": len(judge_operations),
            "judge_review_avg_latency_ms": (
                sum(judge_latencies) / len(judge_latencies) if judge_latencies else 0.0
            ),
            "judge_review_p95_latency_ms": self._p95(judge_latencies),
            "judge_review_total_cost_usd": float(judge_total_cost),
        }

    def history(self) -> list[dict]:
        return [dict(item) for item in self._query_history]

    def operations(self) -> list[dict]:
        return [
            dict(item)
            for item in self._operation_history
            if self._has_model(item.get("model"))
        ]

    def load_state(self) -> bool:
        if self._state_file is None or not self._state_file.exists():
            return False

        try:
            with self._state_file.open("r", encoding="utf-8") as f:
                payload = json.load(f)

            self._sequence = int(payload.get("sequence", 0) or 0)
            self._query_history = [
                item for item in payload.get("query_history", []) if isinstance(item, dict)
            ]
            self._operation_history = [
                item
                for item in payload.get("operation_history", [])
                if isinstance(item, dict) and self._has_model(item.get("model"))
            ]

            # Backfill old saved records where only total_tokens existed and cost was 0.
            for item in self._operation_history:
                prompt_tokens, completion_tokens, total_tokens = self._normalize_token_usage(
                    {
                        "prompt_tokens": item.get("prompt_tokens", 0),
                        "completion_tokens": item.get("completion_tokens", 0),
                        "total_tokens": item.get("total_tokens", 0),
                    }
                )
                item["prompt_tokens"] = prompt_tokens
                item["completion_tokens"] = completion_tokens
                item["total_tokens"] = total_tokens
                item["cost_usd"] = float(
                    self.estimate_cost_usd(
                        str(item.get("model", "")),
                        prompt_tokens,
                        completion_tokens,
                    )
                )

            # Ensure monotonic ids continue after reload.
            max_seen_id = max(
                [self._sequence]
                + [int(item.get("id", 0) or 0) for item in self._query_history]
                + [int(item.get("id", 0) or 0) for item in self._operation_history]
            )
            self._sequence = max_seen_id
            return True
        except Exception:
            self._sequence = 0
            self._query_history = []
            self._operation_history = []
            return False

    def save_state(self) -> None:
        if self._state_file is None:
            return

        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "sequence": self._sequence,
            "query_history": self._query_history,
            "operation_history": self._operation_history,
        }
        with self._state_file.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
