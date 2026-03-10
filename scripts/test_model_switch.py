#!/usr/bin/env python3
"""Test model switch via WebSocket."""
import asyncio, json, websockets

async def test():
    uri = "ws://127.0.0.1:8789?token=12345"
    async with websockets.connect(uri) as ws:
        # 1. Request models
        await ws.send(json.dumps({"type": "models.list"}))
        resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
        while resp.get("type") != "models.list.result":
            resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))

        print("=== CURRENT MODEL ===")
        print("  model:", resp.get("current"))
        print("  provider:", resp.get("provider"))
        print()
        for g in resp.get("groups", []):
            nm = len(g.get("models", []))
            print("  Group: {} (provider={}, count={})".format(g["name"], g["provider"], nm))
            for m in g.get("models", [])[:5]:
                tag = " (active)" if m.get("active") else ""
                print("    -", m["name"], tag)
            if nm > 5:
                print("    ... and {} more".format(nm - 5))

        # 2. Switch to OpenWebUI deepcoder:14b
        print()
        print("=== SWITCHING TO openwebui/deepcoder:14b ===")
        await ws.send(json.dumps({"type": "models.set", "model": "deepcoder:14b", "provider": "openwebui"}))
        resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
        while resp.get("type") != "models.set.result":
            resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
        print("  success:", resp.get("success"))
        print("  model:", resp.get("model"))
        print("  provider:", resp.get("provider"))
        if resp.get("error"):
            print("  ERROR:", resp.get("error"))

        # 3. Send a test message
        print()
        print("=== SENDING TEST MESSAGE ===")
        await ws.send(json.dumps({"type": "message", "text": "Say hello in one sentence", "session_id": "test_switch"}))

        done = False
        while not done:
            try:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=45))
                mtype = msg.get("type", "")
                if mtype == "message.chunk":
                    pass  # streaming token
                elif mtype == "message.done":
                    reply = msg.get("text", "")
                    print("  REPLY:", reply[:300])
                    done = True
                elif mtype == "error":
                    print("  ERROR:", msg.get("text", ""))
                    done = True
                elif mtype == "progress":
                    print("  progress:", msg.get("text", ""))
            except asyncio.TimeoutError:
                print("  TIMEOUT waiting for response")
                done = True

asyncio.run(test())
