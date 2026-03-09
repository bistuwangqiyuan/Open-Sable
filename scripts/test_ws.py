#!/usr/bin/env python3
"""Direct WebSocket test — send a message and wait for response."""
import asyncio, aiohttp, json, time, sys

async def test():
    url = "ws://127.0.0.1:8789/?token=12345"
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(url) as ws:
            await ws.send_json({
                "type": "message",
                "session_id": "test_direct_123",
                "user_id": "desktop",
                "text": "Hello, what is 2+2?"
            })
            print("Sent message, waiting for response...")
            
            start = time.time()
            while time.time() - start < 90:
                try:
                    msg = await asyncio.wait_for(ws.receive_json(), timeout=5)
                    mtype = msg.get("type", "?")
                    print(f"  [{mtype}] {json.dumps(msg)[:200]}")
                    if mtype in ("message.done", "error"):
                        break
                except asyncio.TimeoutError:
                    print(f"  ... waiting ({int(time.time()-start)}s)")
            else:
                print("TIMED OUT after 90s — no response")

asyncio.run(test())
