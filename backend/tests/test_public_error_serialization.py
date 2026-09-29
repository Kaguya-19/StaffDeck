import json

import pytest
from pydantic import BaseModel, ValidationError, model_validator
from starlette.requests import Request
from app.public_api.errors import PublicAPIError, public_api_error_handler

class InvalidGraph(BaseModel):
    start_node_id: str

    @model_validator(mode="after")
    def check_start(self):
        raise ValueError("start_node_id must reference an existing node")

@pytest.mark.asyncio
async def test_public_invalid_graph_errors_remain_structured_and_json_serializable():
    with pytest.raises(ValidationError) as caught:
        InvalidGraph(start_node_id="missing_node")
    request = Request({"type": "http", "method": "POST", "path": "/api/v1/sops", "headers": []})
    request.state.request_id = "graph-rejection"
    response = await public_api_error_handler(request, PublicAPIError(
        422, "INVALID_SOP", "The SOP graph is invalid.", errors=caught.value.errors()))
    payload = json.loads(response.body)
    assert response.status_code == 422
    assert payload["code"] == "INVALID_SOP"
    assert payload["request_id"] == "graph-rejection"
    assert payload["errors"][0]["ctx"]["error"] == "start_node_id must reference an existing node"
