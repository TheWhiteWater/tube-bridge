"""Frozen contract for user-filled research artifact templates and preview tools."""

from __future__ import annotations

import asyncio

from tube_bridge import research_artifacts
from tube_bridge.server import _build_tools, list_tools


RESEARCH_TOOL_NAMES = {
    "research_templates_list",
    "research_scaffold_create",
    "research_artifact_get",
    "research_artifact_save",
    "research_artifacts_list",
    "research_artifact_export",
}


def test_bundled_templates_separate_machine_and_agent_ownership() -> None:
    templates = research_artifacts.list_templates()["templates"]
    assert {item["template_id"] for item in templates} == {
        "structured-source-v1",
        "corpus-study-v1",
    }
    for summary in templates:
        definition = research_artifacts.load_template(summary["template_id"])
        assert definition["field_ownership"] == {
            "machine_fields": "tube_bridge_read_only",
            "agent_fields": "user_or_agent_editable",
        }
        assert isinstance(definition["agent_fields"], dict)
        assert all(
            value in (None, [], {})
            or (isinstance(value, dict) and value.get("completion") == "unfilled")
            for value in definition["agent_fields"].values()
        )


def test_default_runtime_catalog_remains_immutable_seventeen_tools() -> None:
    tools = asyncio.run(list_tools())
    assert len(tools) == 17
    assert not (RESEARCH_TOOL_NAMES & {tool.name for tool in tools})


def test_explicit_preview_catalog_adds_exactly_six_research_tools() -> None:
    tools = _build_tools(include_research=True)
    names = {tool.name for tool in tools}
    assert len(tools) == 23
    assert RESEARCH_TOOL_NAMES <= names

    by_name = {tool.name: tool for tool in tools}
    assert by_name["research_templates_list"].annotations.readOnlyHint is True
    assert by_name["research_scaffold_create"].annotations.readOnlyHint is False
    assert by_name["research_scaffold_create"].annotations.destructiveHint is False
    assert by_name["research_artifact_save"].annotations.readOnlyHint is False
    assert by_name["research_artifact_save"].annotations.destructiveHint is False
    assert by_name["research_artifact_export"].annotations.readOnlyHint is True


def test_preview_tool_schemas_require_stable_targets_and_revision_guards() -> None:
    tools = {tool.name: tool for tool in _build_tools(include_research=True)}

    create = tools["research_scaffold_create"].inputSchema
    assert create["required"] == ["template_id", "target"]
    assert create["properties"]["target"]["additionalProperties"] is False

    save = tools["research_artifact_save"].inputSchema
    assert save["required"] == ["artifact_id", "expected_revision", "agent_fields"]
    assert save["properties"]["expected_revision"]["minimum"] == 1
    assert "machine_fields" not in save["properties"]

    export = tools["research_artifact_export"].inputSchema
    assert set(export["properties"]["format"]["enum"]) == {"json", "csv"}
