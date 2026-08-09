#!/usr/bin/env python3
import asyncio
import json
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

VIDEO_ID = "dQw4w9WgXcQ"
VIDEO_URL = f"https://www.youtube.com/watch?v={VIDEO_ID}"
CHANNEL_ID = "UCuAXFkgsw1L7xaCfnd5JJOw"
CHANNEL_URL = f"https://www.youtube.com/channel/{CHANNEL_ID}"
PLAYLIST_URL = "https://www.youtube.com/playlist?list=UUuAXFkgsw1L7xaCfnd5JJOw"
EXPECTED_TOOLS = {
    "youtube_search", "youtube_search_channels", "youtube_get_channel_info",
    "youtube_get_video_info", "youtube_get_trending", "youtube_get_channel_videos",
    "youtube_get_playlist", "youtube_get_transcript", "youtube_get_available_languages",
    "youtube_get_comments", "corpus_create", "corpus_add", "corpus_search",
    "corpus_list", "corpus_delete", "tube_bridge_help",
}


def classify_error(value: str) -> str:
    lowered = value.lower()
    for token, category in (
        ("quota", "quota"), ("bot", "youtube_bot_detection"),
        ("timeout", "timeout"), ("timed out", "timeout"),
        ("api key", "api_key"), ("http_403", "http_403"),
        ("http_404", "http_404"), ("network", "network"),
        ("transcript", "transcript"), ("model", "embedding_model"),
        ("memory", "resource_limit"), ("not found", "not_found"),
    ):
        if token in lowered:
            return category
    return "remote_tool_error"


def summarize(name: str, data):
    if name == "tube_bridge_help":
        return {"version": data.get("version"), "tool_count": len(data.get("tools", [])), "deploy_field_present": "deploy_url" in data, "private_hostname_present": ".railway.app" in json.dumps(data)}
    if name == "youtube_search":
        return {"source": data.get("source"), "total_results": data.get("total_results", 0)}
    if name == "youtube_search_channels":
        return {"source": data.get("source"), "total_results": data.get("total_results", 0)}
    if name == "youtube_get_channel_info":
        return {"channel_id_matches": data.get("channel_id") == CHANNEL_ID, "video_count_present": data.get("video_count") is not None}
    if name == "youtube_get_video_info":
        return {"video_id_matches": data.get("id") == VIDEO_ID, "title_present": bool(data.get("title"))}
    if name == "youtube_get_trending":
        return {"source": data.get("source"), "total_results": data.get("total_results", 0)}
    if name == "youtube_get_channel_videos":
        return {"total_videos": data.get("total_videos", 0), "warning_present": "_warning" in data}
    if name == "youtube_get_playlist":
        return {"total_videos": data.get("total_videos", 0), "warning_present": "_warning" in data}
    if name == "youtube_get_transcript":
        return {"video_id_matches": data.get("video_id") == VIDEO_ID, "segment_count": data.get("segment_count", 0), "language_present": bool(data.get("language"))}
    if name == "youtube_get_available_languages":
        return {"video_id_matches": data.get("video_id") == VIDEO_ID, "total_languages": data.get("total_languages", 0)}
    if name == "youtube_get_comments":
        return {"video_id_matches": data.get("video_id") == VIDEO_ID, "total_comments": data.get("total_comments", 0)}
    if name in ("corpus_create", "corpus_add", "corpus_delete"):
        return {"status": data.get("status"), "chunks": data.get("chunks")}
    if name == "corpus_search":
        return {"total_results": data.get("total_results", 0)}
    if name == "corpus_list":
        return {"total": data.get("total", 0)}
    return {"response_type": type(data).__name__}


def semantic_pass(name: str, summary: dict) -> bool:
    if name == "tube_bridge_help":
        return summary == {"version": "1.0.3", "tool_count": 16, "deploy_field_present": False, "private_hostname_present": False}
    if name in ("youtube_search", "youtube_search_channels", "youtube_get_trending"):
        return summary["total_results"] > 0
    if name == "youtube_get_channel_info":
        return summary["channel_id_matches"] and summary["video_count_present"]
    if name == "youtube_get_video_info":
        return summary["video_id_matches"] and summary["title_present"]
    if name in ("youtube_get_channel_videos", "youtube_get_playlist"):
        return summary["total_videos"] > 0
    if name == "youtube_get_transcript":
        return summary["video_id_matches"] and summary["segment_count"] > 0 and summary["language_present"]
    if name == "youtube_get_available_languages":
        return summary["video_id_matches"] and summary["total_languages"] > 0
    if name == "youtube_get_comments":
        return summary["video_id_matches"] and summary["total_comments"] > 0
    if name == "corpus_create":
        return summary["status"] in ("created", "already_exists")
    if name == "corpus_add":
        return summary["status"] in ("indexed", "already_indexed") and (summary["chunks"] is None or summary["chunks"] > 0)
    if name == "corpus_search":
        return summary["total_results"] > 0
    if name == "corpus_list":
        return summary["total"] >= 1
    if name == "corpus_delete":
        return summary["status"] == "deleted"
    return True


async def main():
    variables = json.loads(subprocess.run(["railway", "variables", "--json"], capture_output=True, text=True, check=True).stdout)
    domain = variables.get("RAILWAY_PUBLIC_DOMAIN") or variables.get("RAILWAY_STATIC_URL")
    endpoint = (("https://" + domain) if not domain.startswith("http") else domain) + "/mcp"
    auth_key = variables["TUBE_BRIDGE_AUTH_KEY"]
    corpus_id = "pi-smoke-" + uuid.uuid4().hex[:12]
    results = []
    cleanup = {"attempted": False, "passed": False}
    started = datetime.now(timezone.utc).isoformat()

    timeout = httpx.Timeout(420.0, connect=30.0)
    async with httpx.AsyncClient(headers={"Authorization": "Bearer " + auth_key}, timeout=timeout) as client:
        async with streamable_http_client(endpoint, http_client=client) as (read, write, _):
            async with ClientSession(read, write) as session:
                init = await session.initialize()
                catalog = await session.list_tools()
                names = {tool.name for tool in catalog.tools}
                catalog_result = {
                    "name": "mcp_initialize_and_list_tools",
                    "status": "PASS" if names == EXPECTED_TOOLS else "FAIL",
                    "elapsed_seconds": 0,
                    "summary": {
                        "server_name": init.serverInfo.name,
                        "catalog_count": len(names),
                        "exact_catalog": names == EXPECTED_TOOLS,
                    },
                }
                results.append(catalog_result)

                async def call(name, arguments):
                    before = time.monotonic()
                    try:
                        response = await session.call_tool(name, arguments)
                        text = response.content[0].text if response.content else "{}"
                        data = json.loads(text)
                        elapsed = round(time.monotonic() - before, 3)
                        if isinstance(data, dict) and "error" in data:
                            row = {"name": name, "status": "FAIL", "elapsed_seconds": elapsed, "error_category": classify_error(str(data["error"]))}
                        else:
                            summary = summarize(name, data)
                            row = {"name": name, "status": "PASS" if semantic_pass(name, summary) else "FAIL", "elapsed_seconds": elapsed, "summary": summary}
                    except Exception as exc:
                        row = {"name": name, "status": "FAIL", "elapsed_seconds": round(time.monotonic() - before, 3), "error_category": classify_error(str(exc)), "exception_type": type(exc).__name__}
                    results.append(row)
                    return row

                try:
                    await call("tube_bridge_help", {})
                    await call("youtube_search", {"query": "Rick Astley Never Gonna Give You Up", "limit": 2})
                    await call("youtube_search_channels", {"query": "Rick Astley", "limit": 2})
                    await call("youtube_get_channel_info", {"channel_id": CHANNEL_ID})
                    await call("youtube_get_video_info", {"url": VIDEO_URL})
                    await call("youtube_get_trending", {"limit": 2})
                    await call("youtube_get_channel_videos", {"channel_url": CHANNEL_URL, "limit": 2})
                    await call("youtube_get_playlist", {"playlist_url": PLAYLIST_URL, "limit": 2})
                    await call("youtube_get_transcript", {"url": VIDEO_URL, "lang": "en", "with_timestamps": True})
                    await call("youtube_get_available_languages", {"url": VIDEO_URL})
                    await call("youtube_get_comments", {"url": VIDEO_URL, "max_results": 2})
                    await call("corpus_create", {"corpus_id": corpus_id, "label": "Pi Railway MCP smoke"})
                    await call("corpus_add", {"corpus_id": corpus_id, "url": VIDEO_URL})
                    await call("corpus_search", {"corpus_id": corpus_id, "query": "never give up", "top_k": 2})
                    await call("corpus_list", {})
                finally:
                    cleanup["attempted"] = True
                    deleted = await call("corpus_delete", {"corpus_id": corpus_id})
                    cleanup["passed"] = deleted["status"] == "PASS"
                    after = await call("corpus_list", {})
                    post_delete_empty = after.get("summary", {}).get("total") == 0
                    if post_delete_empty:
                        after["status"] = "PASS"
                        after["summary"]["post_delete_empty"] = True
                    cleanup["post_delete_list_called"] = True
                    cleanup["post_delete_empty"] = post_delete_empty

    called = {row["name"] for row in results if row["name"] in EXPECTED_TOOLS}
    failed = [row["name"] for row in results if row["status"] != "PASS"]
    report = {
        "kind": "tube_bridge.private_railway_mcp_live_smoke",
        "version": "0.1",
        "work_item_id": "WI-00072",
        "started_at": started,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "credential_handling": "Railway CLI dynamic retrieval; endpoint and Bearer value omitted from output and receipt.",
        "expected_tool_count": 16,
        "called_all_16_tools": called == EXPECTED_TOOLS,
        "overall_status": "PASS" if not failed and called == EXPECTED_TOOLS and cleanup["passed"] else "FAIL",
        "failed_checks": failed,
        "cleanup": cleanup,
        "results": results,
    }
    Path("/tmp/tube-railway-mcp-smoke-result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return report["overall_status"] == "PASS"


if __name__ == "__main__":
    raise SystemExit(0 if asyncio.run(main()) else 1)
