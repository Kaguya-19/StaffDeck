# Native model environment references

Tenant administrators may configure a model using `secret_ref` instead of
`api_key` through `/api/enterprise/model-configs`. The serving operator supplies
`MODEL_SECRET_BINDINGS` as JSON containing only tenant, alias, environment
variable name, and a non-secret revision:

```json
{"tenant_a":{"discovery":{"env":"STAFFDECK_MODEL_API_KEY","revision":"1"}}}
```

Supply the provider credential in that environment variable inside the serving
process. Do not put its value in the reference metadata or a configuration file.
An administrator can select only an alias bound to their tenant; the API does
not accept arbitrary environment variable names.

Example create body (with normal administrator authentication):

```json
{
  "tenant_id": "tenant_a",
  "name": "Discovery model",
  "api_protocol": "openai_chat_completions",
  "base_url": "https://llm-center.modelbest.co/v1",
  "model": "<operator-selected-model-id>",
  "secret_ref": "discovery",
  "enabled": true,
  "is_default": true
}
```

Use `POST /api/enterprise/model-configs?verify_before_save=true` to run the
existing text, stream, and JSON verification before activation. Without that
option, create remains disabled and unverified. Readback returns `secret_ref`,
`secret_ref_revision`, and `credential_configured`; `api_key_masked` is empty for
references. The database stores no provider credential for this path.

Missing aliases, invalid operator bindings, and absent environment values reject
with `MODEL_SECRET_REFERENCE_NOT_CONFIGURED`, `MODEL_SECRET_BINDING_INVALID`, or
`MODEL_SECRET_REFERENCE_UNAVAILABLE`. Reference and binding changes invalidate
the existing security trust. Increase the binding revision when rotating a
credential. The serving process also detects changes to the bound variable name
or credential value, even if its revision was not changed.

Verification of references belongs to the current serving process. After a
service restart, the persisted alias is readable but runtime use requires new
verification; another worker process cannot inherit that verification. Run
`POST /api/enterprise/model-configs/{id}/test?tenant_id=tenant_a` in the process
that will consume the model, then use the normal update/enable and set-default
API. For an initial sole model, `activate_if_initial=true` on `/test` may activate
it after all probes succeed. Reverification of a changed binding advances the
existing key/security/config revisions and clears enabled/default state first.

To change from a literal key to a reference, PUT `secret_ref`; to change back,
PUT a nonempty `api_key`. Supplying both rejects. The existing literal-key path,
admin/tenant permissions, protocol rules, and enabled/default controls continue
to apply. The SQLite startup migration adds nullable reference columns without
altering existing literal models.

Normal native Knowledge discovery may use this formally verified default model.
This does not enable background discovery for public-host ingestion or require
every upload to generate suggestions. Use normal upload/review operations for
independent runtime acceptance; no suggestion or trust state should be seeded.
