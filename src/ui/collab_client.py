# MBC-2.0 — Shared-console operator client
# Author: CREADDINSCART STUDIO + Mater Work + Loder Hankex + jake + jenmnmer + yig
# Made with CREADDINSCART STUDIO - https://www.shit.pub/studio/
#
# Lets another person join the running swarm console from a second terminal
# (same machine or across the network) and co-manage the bots.
#
#   python -m src.ui.collab_client --host 127.0.0.1 --port 25599 --name Alice
#   python -m src.ui.collab_client --host 10.0.0.5 --port 25599 --name Bob --token SECRET

import argparse
import os
import socket
import sys
import threading


def _setup_streams():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _read_name(default):
    try:
        name = input("operator name: ").strip()
    except (EOFError, KeyboardInterrupt):
        name = ""
    return name or default


def run(host, port, name, token=None):
    _setup_streams()
    try:
        sock = socket.create_connection((host, port), timeout=10)
    except OSError as e:
        print(f"[collab] cannot reach {host}:{port} - {e}")
        return 1

    stop = threading.Event()

    def reader():
        buf = b""
        while not stop.is_set():
            try:
                data = sock.recv(4096)
            except OSError:
                break
            if not data:
                break
            buf += data
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                try:
                    text = line.decode("utf-8", errors="replace").rstrip("\r")
                except Exception:
                    text = repr(line)
                if stop.is_set():
                    return
                try:
                    sys.stdout.write("\r" + text + "\n" + prompt)
                    sys.stdout.flush()
                except (ValueError, OSError):
                    return
        stop.set()

    prompt = f"{name}@mbc> "

    # handshake
    if token:
        sock.sendall((f"AUTH {token}\n").encode("utf-8"))
    sock.sendall((f"NAME {name}\n").encode("utf-8"))

    t = threading.Thread(target=reader, daemon=True)
    t.start()

    print(f"[collab] joined {host}:{port} as {name}. type 'help' for commands, 'quit' to leave.")
    try:
        while not stop.is_set():
            try:
                line = input(prompt)
            except (EOFError, KeyboardInterrupt):
                break
            if not line.strip():
                continue
            try:
                sock.sendall((line + "\n").encode("utf-8"))
            except OSError:
                break
            if line.strip().lower() in ("quit", "exit"):
                break
    finally:
        stop.set()
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            sock.close()
        except OSError:
            pass
        t.join(timeout=1.5)
        print("\n[collab] left the shared console.")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="mbc-collab",
        description="MBC-2.0 - join a shared swarm console as another operator.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="host running MBC-2.0 (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=25599, help="collab port (default 25599)")
    parser.add_argument("--name", default="", help="operator display name")
    parser.add_argument("--token", default=os.environ.get("MBC_COLLAB_TOKEN", ""), help="auth token if the host set one")
    args = parser.parse_args(argv)

    name = args.name or _read_name(f"operator-{os.getpid()}")
    return run(args.host, args.port, name, args.token or None)


if __name__ == "__main__":
    sys.exit(main())
