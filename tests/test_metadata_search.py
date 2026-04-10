from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from geonode_mcp.models.common import ResponseFormat
from geonode_mcp.models.resources import (
    MetadataSearchField,
    MetadataSearchMode,
    MetadataSearchResourceType,
    SearchMetadataTextInput,
)
from geonode_mcp.tools import resources


def test_build_subqueries_for_dataset_title_search() -> None:
    params = SearchMetadataTextInput(
        text="degraded soil",
        resource_types=[MetadataSearchResourceType.DATASET],
        search_in=[MetadataSearchField.TITLE],
    )

    subqueries = resources._build_subqueries(params)

    assert subqueries == [{
        "resource_type": "dataset",
        "field": "title",
        "route_name": "datasets",
        "query_params": {"filter{title.icontains}": "degraded soil"},
    }]


def test_build_subquery_batches_for_fast_any_metadata_search() -> None:
    params = SearchMetadataTextInput(
        text="degraded soil",
        resource_types=[MetadataSearchResourceType.DATASET],
        search_in=[MetadataSearchField.ANY_METADATA],
        search_mode=MetadataSearchMode.FAST,
    )

    batches = resources._build_subquery_batches(params)

    assert len(batches) == 3
    assert [subquery["field"] for subquery in batches[0]] == ["title", "keywords"]
    assert [subquery["field"] for subquery in batches[1]] == ["abstract"]
    assert [subquery["field"] for subquery in batches[2]] == ["extra_metadata"]


def test_search_metadata_text_merges_results_and_tracks_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    async def fake_get(route: str, params: dict[str, object] | None = None) -> dict[str, object]:
        assert params is not None
        calls.append((route, dict(params)))
        if "filter{title.icontains}" in params:
            return {
                "total": 1,
                "datasets": [{
                    "pk": "10",
                    "title": "Degraded soil in the semi-arid region",
                    "date": "2026-03-01T00:00:00-03:00",
                    "raw_abstract": "Thematic map.",
                    "detail_url": "https://example/datasets/10",
                    "owner": {"first_name": "Ana", "last_name": "Silva", "username": "ana"},
                    "resource_type": "dataset",
                    "keywords": [],
                }],
            }
        return {
            "total": 2,
            "datasets": [
                {
                    "pk": "10",
                    "title": "Degraded soil in the semi-arid region",
                    "date": "2026-03-01T00:00:00-03:00",
                    "raw_abstract": "Description mentions degraded soil and erosion risk.",
                    "detail_url": "https://example/datasets/10",
                    "owner": {"first_name": "Ana", "last_name": "Silva", "username": "ana"},
                    "resource_type": "dataset",
                    "keywords": [],
                },
                {
                    "pk": "11",
                    "title": "Erosion index",
                    "date": "2026-02-01T00:00:00-03:00",
                    "raw_abstract": "Description mentions degraded soil in watersheds.",
                    "detail_url": "https://example/datasets/11",
                    "owner": {"first_name": "Bruno", "last_name": "Costa", "username": "bruno"},
                    "resource_type": "dataset",
                    "keywords": [],
                },
            ],
        }

    monkeypatch.setattr(resources.api, "route", lambda name, **_: name)
    monkeypatch.setattr(resources.api, "get", fake_get)

    output = asyncio.run(
        resources.geonode_search_metadata_text(
            SearchMetadataTextInput(
                text="degraded soil",
                resource_types=[MetadataSearchResourceType.DATASET],
                search_in=[MetadataSearchField.TITLE, MetadataSearchField.ABSTRACT],
                response_format=ResponseFormat.JSON,
            )
        )
    )
    payload = json.loads(output)

    assert len(calls) == 2
    assert calls[0][0] == "datasets"
    assert calls[1][0] == "datasets"
    assert payload["total_is_exact"] is False
    assert payload["count"] == 2
    assert payload["results"][0]["id"] == "10"
    assert payload["results"][0]["matched_fields"] == ["title", "abstract"]
    assert payload["results"][1]["matched_fields"] == ["abstract"]


def test_fast_mode_stops_after_first_batch_when_page_is_filled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    async def fake_get(route: str, params: dict[str, object] | None = None) -> dict[str, object]:
        assert params is not None
        calls.append((route, dict(params)))
        if "filter{title.icontains}" in params:
            return {
                "total": 2,
                "datasets": [
                    {
                        "pk": "1",
                        "title": "Degraded soil overview",
                        "date": "2026-03-03T00:00:00-03:00",
                        "raw_abstract": "Title hit.",
                        "detail_url": "https://example/datasets/1",
                        "owner": {"first_name": "Ana", "last_name": "Silva", "username": "ana"},
                        "resource_type": "dataset",
                        "keywords": [],
                    },
                    {
                        "pk": "2",
                        "title": "Degraded soil baseline",
                        "date": "2026-03-02T00:00:00-03:00",
                        "raw_abstract": "Another title hit.",
                        "detail_url": "https://example/datasets/2",
                        "owner": {"first_name": "Ana", "last_name": "Silva", "username": "ana"},
                        "resource_type": "dataset",
                        "keywords": [],
                    },
                ],
            }
        if "filter{keywords.name.icontains}" in params:
            return {"total": 0, "datasets": []}
        raise AssertionError("Fast mode should not execute lower-priority batches.")

    monkeypatch.setattr(resources.api, "route", lambda name, **_: name)
    monkeypatch.setattr(resources.api, "get", fake_get)

    output = asyncio.run(
        resources.geonode_search_metadata_text(
            SearchMetadataTextInput(
                text="degraded soil",
                resource_types=[MetadataSearchResourceType.DATASET],
                search_in=[MetadataSearchField.ANY_METADATA],
                limit=2,
                response_format=ResponseFormat.JSON,
            )
        )
    )
    payload = json.loads(output)

    assert len(calls) == 2
    assert payload["query_plan_executed"] == 2
    assert payload["query_plan_total"] == 4
    assert payload["search_mode"] == "fast"
    assert payload["count"] == 2


def test_search_metadata_text_uses_resources_for_extra_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    async def fake_get(route: str, params: dict[str, object] | None = None) -> dict[str, object]:
        assert params is not None
        calls.append((route, dict(params)))
        return {
            "total": 1,
                "resources": [{
                    "pk": "99",
                    "title": "Recovery map",
                    "date": "2026-03-02T00:00:00-03:00",
                    "detail_url": "https://example/resources/99",
                    "owner": {"first_name": "Celia", "last_name": "Rocha", "username": "celia"},
                    "resource_type": "dataset",
                    "keywords": [],
                }],
        }

    monkeypatch.setattr(resources.api, "route", lambda name, **_: name)
    monkeypatch.setattr(resources.api, "get", fake_get)

    output = asyncio.run(
        resources.geonode_search_metadata_text(
            SearchMetadataTextInput(
                text="environmental preservation",
                resource_types=[MetadataSearchResourceType.DATASET],
                search_in=[MetadataSearchField.EXTRA_METADATA],
                response_format=ResponseFormat.JSON,
            )
        )
    )
    payload = json.loads(output)

    assert len(calls) == 1
    assert calls[0][0] == "resources"
    assert calls[0][1]["filter{resource_type}"] == "dataset"
    assert calls[0][1]["filter{metadata.metadata.icontains}"] == "environmental preservation"
    assert payload["total_is_exact"] is True
    assert payload["results"][0]["matched_fields"] == ["extra_metadata"]


def test_keyword_search_falls_back_to_search_when_filter_is_not_supported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, object]]] = []
    request = httpx.Request("GET", "https://example.test/api/v2/datasets")
    response = httpx.Response(400, request=request)

    async def fake_get(route: str, params: dict[str, object] | None = None) -> dict[str, object]:
        assert params is not None
        calls.append((route, dict(params)))
        if "filter{keywords.name.icontains}" in params:
            raise httpx.HTTPStatusError("bad request", request=request, response=response)
        return {
            "total": 2,
            "datasets": [
                {
                    "pk": "1",
                    "title": "Precision agriculture",
                    "date": "2026-03-03T00:00:00-03:00",
                    "detail_url": "https://example/datasets/1",
                    "owner": {"first_name": "Dora", "last_name": "Lima", "username": "dora"},
                    "resource_type": "dataset",
                    "keywords": [{"name": "Precision Agriculture"}],
                },
                {
                    "pk": "2",
                    "title": "Sensor usage",
                    "date": "2026-03-02T00:00:00-03:00",
                    "detail_url": "https://example/datasets/2",
                    "owner": {"first_name": "Dora", "last_name": "Lima", "username": "dora"},
                    "resource_type": "dataset",
                    "keywords": [{"name": "Remote sensing"}],
                },
            ],
        }

    monkeypatch.setattr(resources.api, "route", lambda name, **_: name)
    monkeypatch.setattr(resources.api, "get", fake_get)

    output = asyncio.run(
        resources.geonode_search_metadata_text(
            SearchMetadataTextInput(
                text="precision agriculture",
                resource_types=[MetadataSearchResourceType.DATASET],
                search_in=[MetadataSearchField.KEYWORDS],
                response_format=ResponseFormat.JSON,
            )
        )
    )
    payload = json.loads(output)

    assert len(calls) == 2
    assert calls[0][1]["filter{keywords.name.icontains}"] == "precision agriculture"
    assert calls[1][1]["search"] == "precision agriculture"
    assert payload["count"] == 1
    assert payload["results"][0]["id"] == "1"


def test_title_search_across_two_types_uses_two_targeted_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    async def fake_get(route: str, params: dict[str, object] | None = None) -> dict[str, object]:
        assert params is not None
        calls.append((route, dict(params)))
        if route == "datasets":
            return {"total": 0, "datasets": []}
        return {"total": 0, "documents": []}

    monkeypatch.setattr(resources.api, "route", lambda name, **_: name)
    monkeypatch.setattr(resources.api, "get", fake_get)

    asyncio.run(
        resources.geonode_search_metadata_text(
            SearchMetadataTextInput(
                text="degraded soil",
                resource_types=[
                    MetadataSearchResourceType.DATASET,
                    MetadataSearchResourceType.DOCUMENT,
                ],
                search_in=[MetadataSearchField.TITLE],
                response_format=ResponseFormat.JSON,
            )
        )
    )

    assert len(calls) == 2
    assert {call[0] for call in calls} == {"datasets", "documents"}
    assert all("filter{title.icontains}" in params for _, params in calls)


def test_exhaustive_mode_executes_all_any_metadata_batches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    async def fake_get(route: str, params: dict[str, object] | None = None) -> dict[str, object]:
        assert params is not None
        calls.append((route, dict(params)))
        if route == "resources":
            return {"total": 0, "resources": []}
        return {"total": 0, "datasets": []}

    monkeypatch.setattr(resources.api, "route", lambda name, **_: name)
    monkeypatch.setattr(resources.api, "get", fake_get)

    output = asyncio.run(
        resources.geonode_search_metadata_text(
            SearchMetadataTextInput(
                text="degraded soil",
                resource_types=[MetadataSearchResourceType.DATASET],
                search_in=[MetadataSearchField.ANY_METADATA],
                search_mode=MetadataSearchMode.EXHAUSTIVE,
                response_format=ResponseFormat.JSON,
            )
        )
    )
    payload = json.loads(output)

    assert len(calls) == 4
    assert payload["query_plan_executed"] == 4
    assert payload["query_plan_total"] == 4
    assert payload["search_mode"] == "exhaustive"
