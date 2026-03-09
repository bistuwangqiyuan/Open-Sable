#!/usr/bin/env python3
"""Quick test: send a tool-triggering query and verify tool_call events.
Uses only stdlib (no 'websockets' package needed)."""
import socket, hashlib, base64, os, json, time, struct, sys

HOST, PORT = "127.0.0.1", 8789
PATH = "/ws?token=12345"

def ws_connect():
    s = socket.create_connection((HOST, PORT), timeout=10)
    key = base64.b64encode(os.urandom(16)).decode()
    req = (
        f"GET {PATH} HTTP/1.1\r\n"
        f"Host: {HOST}:{PORT}\r\n"
        f"Upgrade: websocket\r\n"
        f"Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        f"Sec-WebSocket-Version: 13\r\n\r\n"
    )
    s.sendall(req.encode())
    resp = b""
    while b"\r\n\r\n" not in resp:
        resp += s.recv(4096)
    status = resp.split(b"\r\n")[0].decode()
    if "101" not in status:
        raise RuntimeError(f"WS upgrade failed: {status}")
    print(f"[OK] {status}")
    return s

def ws_recv(s, timeout=15):
    s.settimeout(timeout)
    try:
        header = b""
        while len(header) < 2:
            header += s.recv(2 - len(header))
        length = header[1] & 0x7F
        if length == 126:
            ext = s.recv(2)
            length = struct.unpack("!H", ext)[0]
        elif length == 127:
            ext = s.recv(8)
            length = struct.unpack("!Q", ext)[0]
        data = b""
        while len(data) < length:
            data += s.recv(length - len(data))
        opcode = header[0] & 0x0F
        if opcode == 0x1:
            return data.decode()
        if opcode == 0x9:  # ping→pong
            frame = bytearray([0x8A, 0x80 | len(data)]) + os.urandom(4) + data
            s.sendall(bytes(frame))
            return ws_recv(s, timeout)
        if opcode == 0x8:
            return None
        return data.decode(errors="replace")
    except socket.timeout:
        return None

def ws_send(s, text):
    payload = text.encode()
    mask = os.urandom(4)
    length = len(payload)
    frame = bytearray([0x81])
    if length < 126:
        frame.append(0x80 | length)
    elif length < 65536:
        frame.append(0x80 | 126)
        frame += struct.pack("!H", length)
    else:
        frame.append(0x80 | 127)
        frame += struct.pack("!Q", length)
    frame += mask
    frame += bytearray(b ^ mask[i % 4] for i, b in enumerate(payload))
    s.sendall(bytes(frame))

def main():
    query = sys.argv[1] if len(sys.argv) > 1 else "What's the current BTC price?"
    s = ws_connect()

    # Drain init
    skip = {"connected", "stats", "brain.data", "sessions.list.result",
            "tools.list.result", "model.info", "agents.list.result",
            "models.list.result", "heartbeat"}
    for _ in range(20):
        raw = ws_recv(s, timeout=3)
        if raw is None:
            break
        try:
            d = json.loads(raw)
            t = d.get("type", "")
            if t not in skip:
                print(f"  [init] {t}")
        except json.JSONDecodeError:
            pass

    sid = f"tool_test_{int(time.time())}"
    print(f"\n=== Sending: {query} ===")
    ws_send(s, json.dumps({
        "type": "message",
        "text": query,
        "session_id": sid,
        "user_id": "test"
    }))
    print("--- waiting (up to 120s) ---\n")

    start = time.time()
    seen_types = set()
    for _ in range(120):
        raw = ws_recv(s, timeout=15)
        elapsed = time.time() - start
        if raw is None:
            print(f"\n[TIMEOUT after {elapsed:.1f}s]")
            break
        try:
            d = json.loads(raw)
            t = d.get("type", "")
            seen_types.add(t)
            # Show interesting events
            if t == "progress":
                print(f"  [{t}] ({elapsed:.1f}s) {d.get('text', '')[:200]}")
            elif t == "tool.call":
                print(f"  [TOOL CALL] ({elapsed:.1f}s) {d.get('name', d.get('tool', '?'))}({json.dumps(d.get('args', d.get('arguments', {})))})")
            elif t == "tool.result":
                print(f"  [TOOL RESULT] ({elapsed:.1f}s) {str(d.get('result', ''))[:200]}")
            elif t == "message.done":
                resp = d.get("text", "")
                print(f"\n  [DONE] ({elapsed:.1f}s)")
                print(f"\n--- Response ---\n{resp[:600]}")
                break
            elif t in ("error", "chat.error"):
                print(f"  [ERROR] ({elapsed:.1f}s) {d}")
                break
            elif t == "message.start":
                print(f"  [{t}] ({elapsed:.1f}s)")
            else:
                # Show unknown types for debugging
                if t not in skip:
                    print(f"  [{t}] ({elapsed:.1f}s) {str(d)[:200]}")
        except json.JSONDecodeError:
            print(f"  [raw] ({elapsed:.1f}s) {raw[:200]}")

    s.close()
    print(f"\nEvent types seen: {sorted(seen_types)}")
    print("Done.")

if __name__ == "__main__":
    main()
