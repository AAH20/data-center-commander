"""Every /v2 operation must document its response shape.

The API returned bare dicts for its whole life, so /openapi.json listed 31 paths and
zero response schemas -- an integrator could see that GET /v2/procedures exists and
learn nothing about what comes back. These tests pin the schemas added by
``_declare_response_schemas`` in ``dcc.api_async``.

They exist because the schema declaration is a loop over ``app.routes`` run once at
import: a route added later, or a rename that moves a path out of ``_PAGED_PATHS``,
would drop back to an undocumented response with nothing to notice.
"""

from __future__ import annotations

import pytest

from dcc.api_async import app


@pytest.fixture(scope="module")
def schema() -> dict:
    # The document is cached on first access and the declaration clears the cache at
    # import, so this reflects the declared schemas rather than a partial build.
    return app.openapi()


def _v2_operations(schema: dict) -> list[tuple[str, str, dict]]:
    return [
        (path, verb, operation)
        for path, operations in schema["paths"].items()
        if path.startswith("/v2")
        for verb, operation in operations.items()
    ]


def test_v2_operations_exist(schema: dict) -> None:
    """Guard the parser: an empty or renamed prefix would make every other test vacuous."""
    assert len(_v2_operations(schema)) >= 20


def test_every_v2_operation_documents_a_response(schema: dict) -> None:
    undocumented = [
        f"{verb.upper()} {path}"
        for path, verb, operation in _v2_operations(schema)
        if not (
            operation.get("responses", {})
            .get("200", {})
            .get("content", {})
            .get("application/json", {})
            .get("schema")
        )
    ]
    assert not undocumented, f"{len(undocumented)} /v2 operation(s) with no response schema: {undocumented}"


def test_advisory_envelope_is_declared(schema: dict) -> None:
    """The two fields middleware guarantees are documented on every operation."""
    for path, verb, operation in _v2_operations(schema):
        props = (
            operation["responses"]["200"]["content"]["application/json"]["schema"]
            .get("properties", {})
        )
        assert "read_only" in props, f"{verb.upper()} {path} does not document read_only"
        assert "execution_permitted" in props, f"{verb.upper()} {path} does not document execution_permitted"


def test_paged_routes_document_items_and_cursor(schema: dict) -> None:
    """Cursor-paged endpoints must say so; a caller needs to know to follow next_cursor."""
    for path in ("/v2/procedures", "/v2/dr/policies"):
        props = schema["paths"][path]["get"]["responses"]["200"]["content"]["application/json"][
            "schema"
        ].get("properties", {})
        assert "items" in props, f"{path} does not document items"
        assert "next_cursor" in props, f"{path} does not document next_cursor"


def test_non_paged_route_is_not_documented_as_paged(schema: dict) -> None:
    """Negative control: the envelope choice must actually differ between routes."""
    props = schema["paths"]["/v2/overview"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"].get("properties", {})
    assert "items" not in props
