# UI 0.1.13 incremental integration receipt

Accepted immutable UI source: 32b87446cab4a377fae102567597a32cce5b43c4, parent 972f38cf12be2a7ddd331dd6452a6e04318c5062. Applied only its increment to the integration tree; preserved mounted Host isolation, canonical helpers, ApiError and existing user-content boundaries. Three-page boundary hunks already adopted from 1b201192 remain unchanged. New native Input/Textarea forwardRef and version-detail user boundaries are adopted.

The add/add user-content test conflict retained the prior tests and new version-detail case. A duplicate KnowledgePage USER_CONTENT_ATTRIBUTES import introduced by automatic three-way application was removed after the first focused run; its raw failure is retained.

Focused actual native Host/shared Page/ref/Portal/i18n consumers: 2 files, 7 tests PASS. Log: /Users/a1/Documents/Codex/2026-09-27/g0-g6-integration-intake/ui-wip-handoff/ui-32b87446-integrated-tests.log. First failure: ui-32b87446-integrated-first-failure.log in the same directory. Original immutable patch: ui-32b87446.commit.patch.

C03 dependency finding is already addressed in this integration tree: shared manifest declares tailwind-merge ^3.6.0 (8ca3aa04942cd69e56a3f192cf2418dba8fabf64); native manifest/lock install 3.6.0, and frontend-enterprise/vite.config.ts resolves shared peer imports from its own locked host installation. No shared node_modules or temporary symlink was used. No package/lock change was necessary for this receipt. The package remains source-only with peer dependencies, requiring a host supplying those peers. Full build/typecheck and C03 gate remain pending.

No 674821da presentation follow-up was imported with this receipt. D01–D07/C04, full props coverage, real browser/business persistence, native PEP and runtime presentation remain subject to later owner deliveries and the same final integration. No new candidate, independent acceptance run, deployment or gate upgrade.
