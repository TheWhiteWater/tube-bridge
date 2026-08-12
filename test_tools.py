"""Smoke test for tube-bridge tools."""
import asyncio
from tube_bridge.tools import search, video_info, transcript, trending, playlist
from tube_bridge.youtube.client import extract_video_id


async def test():
    test_video = "jNQXAC9IVRw"

    print("=" * 60)
    print("1. SEARCH: 'python tutorial'")
    r = await search("python tutorial", 3, {})
    print(f"   Source: {r['source']}, Found: {r['total_results']}")
    for v in r["videos"]:
        print(f"   - {v['title'][:60]} | {v['channel']}")

    print("\n" + "=" * 60)
    print("2. VIDEO INFO")
    info = await video_info(test_video)
    print(f"   {info['title']} | {info['view_count']:,} views | {info['duration']}s")

    print("\n" + "=" * 60)
    print("3. TRENDING (top 3)")
    r = await trending(3)
    print(f"   Source: {r.get('source','?')}, Found: {r['total_results']}")
    for v in r["videos"][:3]:
        print(f"   - {v['title'][:60]}")

    print("\n" + "=" * 60)
    print("4. TRANSCRIPT")
    t = await transcript(test_video, None, False)
    print(f"   Lang: {t['language']}, Segments: {t['segment_count']}")
    print(f"   Text: {t['text'][:100]}...")

    print("\n" + "=" * 60)
    print("5. TIMED TRANSCRIPT (first 3 lines)")
    t = await transcript(test_video, None, True)
    for line in t["text"].split("\n")[:3]:
        print(f"   {line}")

    print("\n" + "=" * 60)
    print("ALL DONE ✅")


asyncio.run(test())
