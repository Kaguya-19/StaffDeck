"""Focused contracts for deterministic AgentLoop trace comparison."""
from __future__ import annotations

import unittest

from trace import compare_traces


def lifecycle(kind: str, name: str, call_id: str, sequence: int, *, concurrency_safe: bool) -> dict[str, object]:
    record: dict[str, object] = {
        "kind": kind,
        "scenarioId": "parallel-tools",
        "q": "compare",
        "sequence": sequence,
        "toolCallId": call_id,
        "concurrencySafe": concurrency_safe,
    }
    if kind in {"tool.call", "tool.start", "tool.finish"}:
        record["name"] = name
    else:
        record["result"] = {"type": "success", "toolName": name, "toolCallId": call_id}
    return record


class ConcurrentToolTraceTests(unittest.TestCase):
    def test_concurrent_completion_order_is_compared_by_call_identity(self) -> None:
        native = [
            lifecycle("tool.call", "lookup", "call-lookup", 0, concurrency_safe=True),
            lifecycle("tool.call", "summarize", "call-summarize", 1, concurrency_safe=True),
            lifecycle("tool.result", "lookup", "call-lookup", 2, concurrency_safe=True),
            lifecycle("tool.result", "summarize", "call-summarize", 3, concurrency_safe=True),
        ]
        sidecar = [
            lifecycle("tool.call", "lookup", "call-lookup", 0, concurrency_safe=True),
            lifecycle("tool.call", "summarize", "call-summarize", 1, concurrency_safe=True),
            lifecycle("tool.result", "summarize", "call-summarize", 2, concurrency_safe=True),
            lifecycle("tool.result", "lookup", "call-lookup", 3, concurrency_safe=True),
        ]
        self.assertEqual(compare_traces(native, sidecar), [])

    def test_non_concurrent_completion_order_remains_semantic(self) -> None:
        native = [
            lifecycle("tool.call", "lookup", "call-lookup", 0, concurrency_safe=False),
            lifecycle("tool.call", "summarize", "call-summarize", 1, concurrency_safe=False),
            lifecycle("tool.result", "lookup", "call-lookup", 2, concurrency_safe=False),
            lifecycle("tool.result", "summarize", "call-summarize", 3, concurrency_safe=False),
        ]
        sidecar = [
            lifecycle("tool.call", "lookup", "call-lookup", 0, concurrency_safe=False),
            lifecycle("tool.call", "summarize", "call-summarize", 1, concurrency_safe=False),
            lifecycle("tool.result", "summarize", "call-summarize", 2, concurrency_safe=False),
            lifecycle("tool.result", "lookup", "call-lookup", 3, concurrency_safe=False),
        ]
        self.assertTrue(compare_traces(native, sidecar))

    def test_duplicate_identity_is_not_normalized(self) -> None:
        native = [
            lifecycle("tool.call", "lookup", "call-duplicate", 0, concurrency_safe=True),
            lifecycle("tool.call", "summarize", "call-duplicate", 1, concurrency_safe=True),
            lifecycle("tool.result", "lookup", "call-duplicate", 2, concurrency_safe=True),
            lifecycle("tool.result", "summarize", "call-duplicate", 3, concurrency_safe=True),
        ]
        sidecar = [
            lifecycle("tool.call", "lookup", "call-duplicate", 0, concurrency_safe=True),
            lifecycle("tool.call", "summarize", "call-duplicate", 1, concurrency_safe=True),
            lifecycle("tool.result", "summarize", "call-duplicate", 2, concurrency_safe=True),
            lifecycle("tool.result", "lookup", "call-duplicate", 3, concurrency_safe=True),
        ]
        self.assertTrue(compare_traces(native, sidecar))


if __name__ == "__main__":
    unittest.main()
