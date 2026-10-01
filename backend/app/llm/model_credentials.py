from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from threading import Lock
from uuid import uuid4

from fastapi import HTTPException

from app.config import get_settings


@dataclass(frozen=True)
class SecretBinding:
    env: str
    revision: str
    generation: str
    value: str = field(repr=False)


# Process-only generations make verified references invalid after restart or rotation.
_bindings: dict[tuple[str, str], SecretBinding] = {}
_binding_lock = Lock()


def resolve_secret_binding(tenant_id: str, secret_ref: str) -> SecretBinding:
    binding = get_settings().model_secret_bindings.get(tenant_id, {}).get(secret_ref)
    if not binding:
        raise HTTPException(status_code=422, detail="MODEL_SECRET_REFERENCE_NOT_CONFIGURED")
    env = binding.get("env", "")
    revision = binding.get("revision", "")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", env) or not revision.strip():
        raise HTTPException(status_code=422, detail="MODEL_SECRET_BINDING_INVALID")
    value = os.environ.get(env, "")
    if not value:
        raise HTTPException(status_code=422, detail="MODEL_SECRET_REFERENCE_UNAVAILABLE")
    with _binding_lock:
        previous = _bindings.get((tenant_id, secret_ref))
        if previous and (previous.env, previous.revision, previous.value) == (env, revision, value):
            return previous
        current = SecretBinding(env, revision, uuid4().hex, value)
        _bindings[(tenant_id, secret_ref)] = current
        return current


def model_secret_binding(config) -> SecretBinding | None:
    secret_ref = getattr(config, "secret_ref", None)
    if not secret_ref:
        return None
    binding = resolve_secret_binding(config.tenant_id, secret_ref)
    if binding.revision != config.secret_ref_revision:
        raise HTTPException(status_code=409, detail="MODEL_SECRET_REFERENCE_CHANGED")
    generation = getattr(config, "secret_binding_generation", None)
    if generation is not None and generation != binding.generation:
        raise HTTPException(status_code=409, detail="MODEL_SECRET_REFERENCE_CHANGED")
    return binding
