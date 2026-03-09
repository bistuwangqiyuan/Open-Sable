#!/usr/bin/env python3
"""Quick test: send 'hello' via raw socket and see if we get a response.
Uses only stdlib (no 'websockets' package needed)."""
import socket, hashlib, base64, os, json, time, struct

HOST, PORT = "127.0.0.1", 8789
PATH = "/ws?token=12345"

def ws_connect():
    """Open a WebSocket connection using raw sockets + HTTP upgrade."""
    s = socket.create_connection((HOST, PORT), timeout=10)
    key = base64.b64encode(os.urandom(16)).decode()
    req = (
        f"GET {PATH} HTTP/1.1\r\n"
        f"Host: {HOST}:{PORT}\r\n"
        f"Upgrade: websocket\r\n"
        f"Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        f"Sec-WebSocket-Version: 13\r\n"
        f"\r\n"
    )
    s.sendall(req.encode())
    resp = b""
    while b"\r\n\r\n" not in resp:
        resp += s.recv(4096)
    status_line = resp.split(b"\r\n")[0].decode()
    if "101" not in status_line:
        raise RuntimeError(f"WS upgrade failed: {status_line}")
    print(f"[OK] WebSocket upgrade: {status_line}")
    return s

def ws_recv(s, timeout=15):
    """Read one WebSocket text frame. Returns decoded string or None on timeout."""
    s.settimeout(timeout)
    try:
        header = b""
        while len(header) < 2:
            header += s.recv(2 - len(header))
        opcode = header[0] & 0x0F
        length = header[1] & 0x7F
        if length == 126:
            ext = b""
            while len(ext) < 2:
                ext += s.recv(2 - len(ext))
            length = struct.unpack("!H", ext)[0]
        elif length == 127:
            ext = b""
            while len(ext) < 8:
                ext += s.recv(8 - len(ext))
            length = struct.unpack("!Q", ext)[0]
        data = b""
        while len(data) < length:
            data += s.recv(length - len(data))
        if opcode == 0x1:  # text
            return data.decode()
        if opcode == 0x8:  # close
            return None
        if opcode == 0x9:  # ping → send pong
            ws_send_pong(s, data)
            return ws_recv(s, timeout)
        return data.decode(errors="replace")
    except socket.timeout:
        return None

def ws_send_pong(s, data):
    frame = bytearray([0x8A, 0x80 | len(data)]) + os.urandom(4) + data
    s.sendall(bytes(frame))

def ws_send(s, text):
    """Send a masked WebSocket text frame."""
    payload = text.encode()
    mask = os.urandom(4)
    length = len(payload)
    frame = bytearray([0x81])  # FIN + text
    if length < 126:
        frame.append(0x80 | length)
    elif length < 65536:
        frame.append(0x80 | 126)
        frame += struct.pack("!H", length)
    else:
        frame.append(0x80 | 127)
        frame += struct.pack("!Q", length)
    frame += mask
    masked = bytearray(b ^ mask[i % 4] for i, b in enumerate(payload))
    frame += masked
    s.sendall(bytes(frame))

def main():
    s = ws_connect()

    # Drain init messages (connected, stats, brain.data etc.)
    skip = {"connected", "stats", "brain.data", "sessions.list.result",
            "tools.list.result", "model.info", "agents.list.result",
            "models.list.result"}
    print("--- draining init messages ---")
    for _ in range(20):
        raw = ws_recv(s, timeout=3)
        if raw is None:
            break
        try:
            d = json.loads(raw)
            t = d.get("type", "")
            if t not in skip:
                print(f"  [init] {t}: {str(d)[:150]}")
        except json.JSONDecodeError:
            print(f"  [init raw] {raw[:150]}")

    # Send hello
    msg = json.dumps({
        "type": "message",
        "text": "hello",
        "session_id": "test_ws_hello",
        "user_id": "test"
    })
    print(f"\n--- sending: hello ---")
    ws_send(s, msg)
    print("--- waiting for response (up to 90s) ---\n")

    start = time.time()
    for _ in range(60):
        raw = ws_recv(s, timeout=15)
        elapsed = time.time() - start
        if raw is None:
            print(f"[TIMEOUT after {elapsed:.1f}s - no more data]")
            break
        try:
            d = json.loads(raw)
            t = d.get("type", "")
            print(f"  [{t}] ({elapsed:.1f}s) {str(d)[:250]}")
            if t in ("message.done", "error", "chat.error"):
                break
        except json.JSONDecodeError:
            print(f"  [raw] ({elapsed:.1f}s) {raw[:250]}")

    s.close()
    print("\nDone.")

if __name__ == "__main__":
    main()
