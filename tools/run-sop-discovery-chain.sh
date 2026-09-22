#!/usr/bin/env bash
set -euo pipefail

STAFFDECK_ROOT="${STAFFDECK_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PILOTDECK_ROOT="${PILOTDECK_ROOT:?Set PILOTDECK_ROOT to the final PilotDeck checkout}"
HARNESS_V3_ROOT="${HARNESS_V3_ROOT:?Set HARNESS_V3_ROOT to a built Harness v3 checkout}"
DATABASE_URL="${DATABASE_URL:?Set DATABASE_URL to the isolated StaffDeck database}"
APP_SECRET="${APP_SECRET:?Set APP_SECRET for the isolated StaffDeck database}"
APP_PORT="${APP_PORT:-16223}"
STAFFDECK_URL="${STAFFDECK_URL:-http://127.0.0.1:${APP_PORT}}"
STAFFDECK_AGENT_ID="${STAFFDECK_AGENT_ID:-agent_tenant_demo_overall}"
STAFFDECK_SOP_API_KEY_ENV="${STAFFDECK_SOP_API_KEY_ENV:-STAFFDECK_SOP_API_KEY}"
OUTPUT="${OUTPUT:-${STAFFDECK_ROOT}/evidence/sop-discovery-chain.json}"
NODE_BIN="${NODE_BIN:-node}"
PILOTDECK_BUNDLE="${PILOTDECK_BUNDLE:-${PILOTDECK_ROOT}/fixtures/staffdeck-sop-discovery-bundle.json}"

api_key="${!STAFFDECK_SOP_API_KEY_ENV-}"
if [[ -z "${api_key}" ]]; then
  mkdir -p "$(dirname "${OUTPUT}")"
  printf '{"status":"BLOCKED","reason":"missing_api_key","apiKeyEnv":"%s"}\n' "${STAFFDECK_SOP_API_KEY_ENV}" > "${OUTPUT}"
  echo "BLOCKED: ${STAFFDECK_SOP_API_KEY_ENV} is not set; no credential value was written." >&2
  exit 2
fi

run_dir="$(mktemp -d "${TMPDIR:-/tmp}/staffdeck-sop-chain.XXXXXX")"
harness_home="${HARNESS_V3_HOME:-${run_dir}/harness-home}"
mkdir -p "${harness_home}"
app_log="${run_dir}/staffdeck-app.log"
cleanup() {
  if [[ -n "${app_pid:-}" ]] && kill -0 "${app_pid}" 2>/dev/null; then
    kill "${app_pid}" 2>/dev/null || true
    wait "${app_pid}" 2>/dev/null || true
  fi
  rm -rf "${run_dir}"
}
trap cleanup EXIT INT TERM

(
  cd "${STAFFDECK_ROOT}/backend"
  DATABASE_URL="${DATABASE_URL}" \
  APP_SECRET="${APP_SECRET}" \
  HARNESS_V3_ROOT="${HARNESS_V3_ROOT}" \
  HARNESS_V3_HOME="${harness_home}" \
  DEMO_SEED_ENABLED=false \
  "${STAFFDECK_ROOT}/backend/.venv/bin/python" -m uvicorn app.main:app --host 127.0.0.1 --port "${APP_PORT}"
) >"${app_log}" 2>&1 &
app_pid=$!

for _ in $(seq 1 120); do
  if curl -sS "${STAFFDECK_URL}/" -o /dev/null 2>/dev/null; then break; fi
  sleep 0.25
done
if ! curl -sS "${STAFFDECK_URL}/" -o /dev/null 2>/dev/null; then
  echo "StaffDeck did not become ready; see ${app_log}" >&2
  exit 1
fi

env "${STAFFDECK_SOP_API_KEY_ENV}=${api_key}" \
  "${NODE_BIN}" "${PILOTDECK_ROOT}/scripts/staffdeck-sop-discovery-chain.mjs" \
  --staffdeck-url "${STAFFDECK_URL}" \
  --agent-id "${STAFFDECK_AGENT_ID}" \
  --api-key-env "${STAFFDECK_SOP_API_KEY_ENV}" \
  --bundle "${PILOTDECK_BUNDLE}" \
  --output "${OUTPUT}"
