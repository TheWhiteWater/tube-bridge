"""Smoke test for yt-mcp server tools without launching MCP."""
import asyncio
import json
import sys
sys.path.insert(0, "/home/ali/Workspace/yt-mcp")

from server import _search, _video_info, _trending, _transcript, _available_languages, _extract_video_id, _channel_videos, _playlist


async def test():
    test_video = "https://www.youtube.com/watch?v=jNQXAC9IVRw"  # "Me at the zoo" — first YouTube video
    video_id = _extract_video_id(test_video)

    print("=" * 60)
    print("1. SEARCH: 'python tutorial'")
    result = await _search("python tutorial", limit=3, args={})
    print(f"   Found: {result['total_results']} videos")
    for v in result["videos"]:
        print(f"   - {v['title'][:60]} | {v['channel']} | {v['view_count']:,} views")

    print("\n" + "=" * 60)
    print("2. VIDEO INFO")
    try:
        info = await _video_info(video_id)
        print(f"   Title: {info['title']}")
        print(f"   Channel: {info.get('channel')}")
        print(f"   Duration: {info.get('duration')}s")
        print(f"   Views: {info.get('view_count', 'N/A')}")
    except Exception as e:
        print(f"   ERROR: {e}")

    print("\n" + "=" * 60)
    print("3. TRENDING (top 3)")
    try:
        result = await _trending(limit=3)
        print(f"   Found: {result['total_results']} videos")
        for v in result["videos"]:
            print(f"   - {v['title'][:60]}")
    except Exception as e:
        print(f"   ERROR: {e}")

    print("\n" + "=" * 60)
    print("4. AVAILABLE LANGUAGES")
    try:
        langs = await _available_languages(video_id)
        print(f"   Found: {langs['total_languages']} languages")
        for l in langs.get("languages", []):
            gen = " [AUTO]" if l.get("is_generated") else ""
            print(f"   - {l['language_code']}: {l['language']}{gen}")
    except Exception as e:
        print(f"   ERROR: {e}")

    print("\n" + "=" * 60)
    print("5. TRANSCRIPT (first 200 chars)")
    try:
        result = await _transcript(video_id, lang=None)
        print(f"   Language: {result['language']}")
        print(f"   Segments: {result['segment_count']}")
        print(f"   Text: {result['text'][:200]}...")
    except Exception as e:
        print(f"   ERROR: {e}")

    print("\n" + "=" * 60)
    print("6. TIMED TRANSCRIPT (first 3 lines)")
    try:
        result = await _transcript(video_id, lang=None, with_timestamps=True)
        lines = result["text"].split("\n")[:3]
        for line in lines:
            print(f"   {line}")
    except Exception as e:
        print(f"   ERROR: {e}")

    print("\n" + "=" * 60)
    print("ALL DONE ✅")


asyncio.run(test())
