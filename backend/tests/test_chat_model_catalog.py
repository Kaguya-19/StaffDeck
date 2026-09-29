from types import SimpleNamespace
import json

import httpx
import pytest
from fastapi import HTTPException

from app.api.chat import list_chat_models
from app.public_api import pilotdeck_domain_host as binding
from app.public_api.pilotdeck_domain_binding import FixedPilotDeckDomainHostClient
from app.public_api.pilotdeck_harness_model import select_harness_model


def test_normal_chat_catalog_projects_the_actual_host_id_and_preserves_explicit_selection(monkeypatch):
    calls = []
    def handle(request):
        payload = json.loads(request.content)
        calls.append(payload)
        assert payload['principal'] == {'pilotDeckUserId': 'pd', 'tenantId': 'tenant', 'actorUserId': 'actor', 'agentId': 'target'}
        if request.url.path.endswith('/describe'):
            return httpx.Response(200, json={'operations': ['list_model_catalog', 'model_prepare', 'model_stream']})
        assert payload['operation'] == 'list_model_catalog'
        return httpx.Response(200, json={'data': [{'id': 'provider/model', 'provider': 'provider', 'model': 'model', 'available': True, 'is_default': True}],
                                       'defaultSelection': {'mode': 'model', 'provider': 'provider', 'model': 'model'}})
    host = FixedPilotDeckDomainHostClient('http://pd', 'service', 'pd', httpx.MockTransport(handle), 'tenant', 'actor', 'target')
    monkeypatch.setattr(binding, '_bound_client', host)
    monkeypatch.setenv('PILOTDECK_DOMAIN_HOST_ENABLED', 'true')
    user = SimpleNamespace(tenant_id='tenant', id='actor')
    rows = list_chat_models('tenant', None, user)
    assert rows == [{'id': 'provider/model', 'tenant_id': 'tenant', 'name': 'model', 'provider': 'provider', 'model': 'model',
                     'is_default': True, 'enabled': True, 'source': 'pilotdeck'}]
    context = SimpleNamespace(tenant_id='tenant', user_id='actor', staff_id='target')
    assert select_harness_model(context, rows[0]['id']).id == rows[0]['id']
    with pytest.raises(RuntimeError, match='PUBLIC_HOST_EXPLICIT_MODEL_NOT_SELECTED'):
        select_harness_model(context, 'model_native_config')
    before = len(calls)
    with pytest.raises(HTTPException) as denied:
        list_chat_models('tenant', None, SimpleNamespace(tenant_id='tenant', id='foreign'))
    assert denied.value.status_code == 403
    assert len(calls) == before
    monkeypatch.setattr(binding, '_bound_client', None)
    with pytest.raises(HTTPException) as missing:
        list_chat_models('tenant', None, user)
    assert missing.value.status_code == 503
