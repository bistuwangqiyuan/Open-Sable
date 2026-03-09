#!/usr/bin/env python3
"""Quick test: verify sessions.list now includes last_message and last_response."""
import asyncio, aiohttp

async def test():
    url = "ws://127.0.0.1:8789/?token=12345"
    async with aiohttp.ClientSession() as s:
        async with s.ws_connect(url) as ws:
            msg = await ws.receive_json()
            print(f"connected: v{msg.get('version')}")

            # Request sessions list
            await ws.send_json({"type": "sessions.list"})

            while True:
                msg = await asyncio.wait_for(ws.receive_json(), 30)
                t = msg.get("type", "")
                if t == "sessions.list.result":
                    sessions = msg.get("sessions", [])
                    print(f"Sessions: {len(sessions)}")
                    for s0 in sessions[:3]:
                        print(f"\n  title: {s0.get('title','')[:50]}")
                        print(f"  last_message:  {repr(s0.get('last_message','')[:60])}")
                        print(f"  last_response: {repr(s0.get('last_response','')[:80])}")
                        print(f"  message_count: {s0.get('message_count')}")
                    break

asyncio.run(test())
