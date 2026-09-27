# PD approval root binding

Public SD56c6fb60 adds the public PD approval router and actual httpx client. Integration's `pilotdeck_approval_binding.py` consumes private deployment env to inject that client in `create_public_api_app`; native chat handoffs are untouched.

Set `PILOTDECK_APPROVAL_BRIDGE_ENABLED=true` only for the configured deployment. Required values: `PILOTDECK_GATEWAY_URL`, absolute `PILOTDECK_GATEWAY_TOKEN_PATH`, `STAFFDECK_COPY_TENANT_ID`, `STAFFDECK_COPY_TARGET_AGENT_ID`, all from normal deployment/bootstrap. The service key is read from the normal Gateway-generated token file. No token generation, default global credential or auth bypass is provided. ws/wss maps to the same HTTP/HTTPS Gateway origin. The user's normal SD Bearer is conveyed separately by the public client's X-StaffDeck-Approver-Authorization header.

Focused root tests2/2 passed and syntax checked; these are config/transport fixtures, not an actual mapped profile or approval. Missing enabled config/token fails explicitly. Independent preparation creates fresh identities only through the recorded normal native process; no old account/key/DB is copied.

**Source consumer failure retained:** the public router `_binding` currently accesses `user.disabled`, which the original native User model lacks. The same-tenant native fixture raises AttributeError; original raw at `/Users/a1/Documents/Codex/2026-09-27/g0-g6-integration-intake/approval-sd-native-consumer-first-fail.log`. That narrow router compatibility repair remains public owner responsibility and is not silently patched here.

**Mapping source missing:** ExternalSessionBinding.external_session_id is not proof of a PD sessionKey/project/owner mapping. PD's current session metadata/SOP state likewise lacks a complete authenticated SDtenant/target/PDowner linkage. The new PD bridge rejects an absent authority resolver with SOP_APPROVAL_SESSION_MAPPING_UNAVAILABLE and does not fabricate IDs, mapping files, waits or receipts.

Concentrated entry/DTO/source gaps and consumer evidence are maintained in [public-approval-gateway-integration.md](/Users/a1/Documents/Codex/2026-09-27/g0-g6-integration-intake/sdk-worktrees/pilotdeck/docs/validation/public-approval-gateway-integration.md); public domain/router DELIVERY remains authoritative for its implementation. Existing ownership and the19 provider/DI/profile dependencies continue. No business run, candidate/gate upgrade, push/merge/deploy.
