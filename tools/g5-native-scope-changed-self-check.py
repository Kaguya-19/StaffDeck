#!/usr/bin/env python3
"""Run the implementation-side G5 scope-change checks in this checkout.

This runner deliberately uses local deterministic tests only.  Real-provider artifacts from
the independent acceptance tree are recorded as provenance, never regenerated or overwritten.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ORDINARY_INPUT = (
    "请帮我梳理项目计划，目标是完成验证交付，目前处于验证阶段，暂时没有已知阻塞。"
    "范围和交付日期需要调整，请评估影响并在需要时请负责人确认，确认后继续完成计划。"
)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default=str(root / "evidence/g5-native-scope-changed-self-check.json"),
    )
    args = parser.parse_args()

    python = root / "backend/.venv/bin/python"
    env = os.environ.copy()
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    env["PYTHONPATH"] = ":".join(
        [
            str(root / "backend"),
            str(root / "backend/src"),
            str(root / "portable_sop/src"),
            "/Users/a1/Desktop/claw/openbmb/deepseek-harness-dsh-v0.1.2-alpha.2/python/sdk/src",
        ]
    )
    commands = [
        [
            str(python),
            "-m",
            "pytest",
            "-p",
            "no:capture",
            "-q",
            "backend/tests_harness/test_engine_turn_ownership.py",
            "backend/tests_harness/test_runtime_completion_control.py",
            "backend/tests_harness/test_capability_host_hardening.py",
        ],
        [
            str(python),
            "-m",
            "pytest",
            "-p",
            "no:capture",
            "-q",
            "backend/tests_harness/modules/test_sop_lifecycle_boundary.py",
            "backend/tests_harness/modules/test_sop_runtime.py",
            "backend/tests_harness/test_handoff_source_boundary.py",
            "backend/tests_harness/test_handoff_core.py",
            "backend/tests_harness/test_execution_context_lifecycle.py",
        ],
        [
            str(python),
            "-m",
            "pytest",
            "-p",
            "no:capture",
            "-q",
            "portable_sop/tests",
        ],
    ]

    checks = []
    for command in commands:
        completed = subprocess.run(command, cwd=root, env=env, text=True, capture_output=True)
        checks.append(
            {
                "command": " ".join(command),
                "exit_code": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }
        )

    payload = {
        "evidence_role": "implementation-side self-validation",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "checkout": str(root),
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
        "ordinary_user_input": ORDINARY_INPUT,
        "checks": checks,
        "independent_artifacts_read_only": [
            "/Users/a1/Documents/Codex/2026-09-23/g5-runtime-independent-fe2f7cbd/native-scope-changed-independent.json",
            "/Users/a1/Documents/Codex/2026-09-23/g5-runtime-independent-fe2f7cbd/native-scope-changed-fixed-glue-v2.json",
        ],
        "independent_claim": "not a PASS: real-provider handoff/resume remains for a separate acceptance rerun",
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return 0 if all(item["exit_code"] == 0 for item in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
