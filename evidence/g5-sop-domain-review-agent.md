# G5 SOP Domain Review

This evidence belongs to the isolated StaffDeck worktree created for the G5
domain task.

## Baseline

- Source: `StaffDeck-shared-business-ui`
- Branch: `codex/g5-sop-agent-sd`
- Commit: `f41c8524bd129bcaea96f4f774d97a931e566636`
- Worktree: `/Users/a1/Desktop/claw/openbmb/StaffDeck-g5-sop-agent`
- Source worktree was clean before this evidence-only change.

## Reviewed Contracts

- `backend/app/public_api/sops.py` owns draft creation, ETag guarded replace/
  patch, validation, publish, archive, version listing/diff, and rollback.
- `backend/src/staffdeck_harness/sop/lifecycle.py` and `host.py` own the
  waiting, resume, advance, handoff, and terminal transitions for one SOP
  execution instance.
- `backend/src/staffdeck_harness/modules/*sop*` keeps the runtime provider
  behind the `sop.lifecycle/v2` slot and explicit policy operations.
- `portable_sop/src/staffdeck_sop_runtime/api.py` exposes the independent
  `sop-http-v2` protocol; it does not import PilotDeck internals or access its
  database.

## Focused Verification

Command attempted from this worktree:

```sh
cd /Users/a1/Desktop/claw/openbmb/StaffDeck-g5-sop-agent/backend
uv run --with pytest pytest -q tests/test_public_api_v1.py \
  tests/test_runtime_lock.py tests/test_imported_sop_read.py tests/test_sop_nesting.py
```

Result: **BLOCKED by environment**. The isolated uv environment installed the
declared package and pytest, but the pytest process exited with code 139 before
reporting test results. No test result is counted as PASS.

Diagnosis: `PYTHONFAULTHANDLER=1 uv run pytest -vv -s
tests/test_imported_sop_read.py` consistently faults inside pytest's macOS
capture initialization (`_pytest/capture.py:_readline_workaround`), while the
same environment imports `app.public_api.sops` and reports SQLite `3.45.1`
successfully. This is a test-runner/native capture failure, not a claimed SOP
behavior result.

The existing tracked SOP/runtime tests remain the intended rerun set after the
host's Python/SQLAlchemy native runtime is repaired. No database, status, or
runtime event was fabricated by this task.

## G5 Version Lineage

The StaffDeck shared editor first showed the separate local branch
`project_delivery_plan@1.1.0`, containing 2 nodes and 1 edge
(`n1_collect -> n2_plan`). For the primary chain, the page was then edited to
4 nodes and 4 edges, saved through its save-version dialog as local `1.2.0`,
reloaded, and published through the page's normal “发布到广场” confirmation.
The publish response and subsequent version-management GET returned active
`project_delivery_plan@1.2.0` with the page-authored graph:
`n1_collect -> build_plan`, `build_plan -> confirm_scope/finalize_plan`, and
`confirm_scope -> finalize_plan`.

PilotDeck's shared editor independently retained the same 4-node/4-edge
authoring topology at UI version `1.1.0`. The primary run consumed the
StaffDeck page-published `1.2.0` response directly; the earlier management-only
`1.0.2` run is supplemental and not used to bridge this UI chain.
