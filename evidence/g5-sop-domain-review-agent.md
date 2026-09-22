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

The existing tracked SOP/runtime tests remain the intended rerun set after the
host's Python/SQLAlchemy native runtime is repaired. No database, status, or
runtime event was fabricated by this task.
