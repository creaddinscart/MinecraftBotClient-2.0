# MBC-2.0 — Collaborative Multi-Operator Terminal Hub
# Author: CREADDINSCART STUDIO + Mater Work + Loder Hankex + jake + jenmnmer + yig
# Made with CREADDINSCART STUDIO - https://www.shit.pub/studio/
#
# MBC-2.0 headline feature. Several operators connect to ONE running swarm
# console over TCP and jointly drive a large bot fleet from a shared command
# bus. Every event (bot joins/leaves, broadcasts, operator presence) is mirrored
# to the host terminal and to every connected operator, so the whole team sees
# the same swarm. Standard library only - no extra dependencies.

import socket
import threading
import time

from src import i18n


class OperatorSession:
    def __init__(self, conn, addr, name, is_host=False):
        self.conn = conn
        self.addr = addr
        self.name = name
        self.is_host = is_host
        self.joined = time.time()
        self.lock = threading.Lock()
        self.alive = True

    def send(self, line):
        if not self.alive:
            return
        try:
            with self.lock:
                data = (line.rstrip("\n") + "\n").encode("utf-8", errors="replace")
                self.conn.sendall(data)
        except OSError:
            self.alive = False

    def close(self):
        self.alive = False
        try:
            self.conn.close()
        except OSError:
            pass


class OperatorHub:
    """A TCP hub that turns the single-user swarm console into a shared,
    multi-operator control room."""

    def __init__(self, swarm, settings, host_print, port=None, token=None, log_func=None):
        self.swarm = swarm
        self.settings = settings
        self.host_print = host_print          # prints to the host terminal
        self.log_func = log_func or (lambda m: None)
        self.port = int(port if port is not None else settings.get("collab_port", 25599))
        self.token = str(token if token is not None else settings.get("collab_token", "") or "")
        self.sessions = []
        self._sessions_lock = threading.Lock()
        self._cmd_lock = threading.RLock()    # serialises swarm mutations
        self._server = None
        self._accept_thread = None
        self._stop = threading.Event()
        self.bound_port = None

    # ---- lifecycle --------------------------------------------------------
    def start(self):
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            host = str(self.settings.get("collab_bind", "0.0.0.0") or "0.0.0.0")
            srv.bind((host, self.port))
            srv.listen(16)
            srv.settimeout(1.0)
        except OSError as e:
            msg = i18n.t('label_collab_bind_fail', err=str(e))
            self.host_print(msg)
            self.log_func(msg)
            return False

        self._server = srv
        self.bound_port = srv.getsockname()[1]
        self._accept_thread = threading.Thread(target=self._accept_loop, daemon=True, name="mbc-collab-accept")
        self._accept_thread.start()
        banner = i18n.t('label_collab_listening', port=self.bound_port)
        self.host_print(banner)
        self.log_func(banner)
        return True

    def stop(self):
        self._stop.set()
        if self._server:
            try:
                self._server.close()
            except OSError:
                pass
        with self._sessions_lock:
            for s in list(self.sessions):
                s.close()
            self.sessions.clear()

    # ---- fan-out ----------------------------------------------------------
    def emit(self, line):
        """Mirror a swarm/console event to the host terminal and every operator."""
        if line is None:
            return
        self.host_print(line)
        self._fanout(line)

    def _fanout(self, line):
        with self._sessions_lock:
            targets = list(self.sessions)
        for s in targets:
            s.send(line)

    def announce(self, line):
        """System notice to operators + host (presence, join/leave)."""
        self.host_print(line)
        self.log_func(line)
        self._fanout(line)

    # ---- accept -----------------------------------------------------------
    def _accept_loop(self):
        while not self._stop.is_set():
            try:
                conn, addr = self._server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            conn.settimeout(None)
            t = threading.Thread(target=self._serve, args=(conn, addr), daemon=True, name="mbc-collab-client")
            t.start()

    def _serve(self, conn, addr):
        # Handshake: optional AUTH line then a NAME line (or a bare name).
        try:
            rf = conn.makefile("r", encoding="utf-8", errors="replace")
        except OSError:
            conn.close()
            return

        name = None
        try:
            if self.token:
                first = (rf.readline() or "").strip()
                if first.lower().startswith("auth "):
                    supplied = first[5:].strip()
                    if supplied != self.token:
                        conn.sendall((i18n.t('label_collab_bad_token') + "\n").encode("utf-8"))
                        conn.close()
                        return
                    name = (rf.readline() or "").strip()
                else:
                    conn.sendall((i18n.t('label_collab_auth_required') + "\n").encode("utf-8"))
                    conn.close()
                    return
            else:
                name = (rf.readline() or "").strip()
        except OSError:
            conn.close()
            return

        if name.lower().startswith("name "):
            name = name[5:].strip()
        if not name:
            name = f"operator-{addr[0]}:{addr[1]}"
        name = name[:24]

        session = OperatorSession(conn, addr, name)
        with self._sessions_lock:
            self.sessions.append(session)

        session.send(i18n.t('label_collab_welcome', port=self.bound_port))
        session.send(self._render_help())
        self.announce(i18n.t('label_collab_user_joined', name=name, count=self._operator_count()))
        self._status_to(session)

        try:
            for raw in rf:
                line = raw.rstrip("\r\n")
                if not line.strip():
                    continue
                reply = self.handle_command(session, line)
                if reply is None:      # quit
                    break
                if reply:
                    session.send(reply)
        except OSError:
            pass
        finally:
            with self._sessions_lock:
                if session in self.sessions:
                    self.sessions.remove(session)
            session.close()
            self.announce(i18n.t('label_collab_user_left', name=name, count=self._operator_count()))

    # ---- command bus ------------------------------------------------------
    def handle_command(self, session, line):
        line = line.strip()
        parts = line.split(None, 1)
        cmd = parts[0].lower() if parts else ""
        arg = parts[1].strip() if len(parts) > 1 else ""
        who = session.name
        with self._cmd_lock:
            if cmd in ("help", "?"):
                return self._render_help()
            if cmd == "status":
                return i18n.t('label_swarm_status', alive=self.swarm.alive_count(), total=self.swarm.total_count())
            if cmd == "list":
                return self._render_list()
            if cmd == "who":
                return self._render_who()
            if cmd == "say":
                if not arg:
                    return i18n.t('label_swarm_say_usage')
                sent = self.swarm.say(arg, "alive")
                self.announce(i18n.t('label_collab_say', name=who, count=sent, text=arg))
                return ""
            if cmd in ("msg", "to"):
                sp = arg.split(None, 1)
                if len(sp) < 2:
                    return i18n.t('label_collab_msg_usage')
                selector, text = sp[0], sp[1]
                sent = self.swarm.say_to(selector, text)
                self.announce(i18n.t('label_collab_msg', name=who, selector=selector, count=sent, text=text))
                return ""
            if cmd == "add":
                try:
                    n = int(arg)
                except ValueError:
                    return i18n.t('label_collab_add_usage')
                if n <= 0:
                    return i18n.t('label_collab_add_usage')
                launched = self.swarm.add_bots(n)
                self.announce(i18n.t('label_collab_add', name=who, count=len(launched),
                                     alive=self.swarm.alive_count(), total=self.swarm.total_count()))
                return ""
            if cmd == "kick":
                selector = arg or "all"
                removed = self.swarm.kick(selector)
                self.announce(i18n.t('label_collab_kick', name=who, selector=selector, count=removed))
                return ""
            if cmd == "nick":
                if not arg:
                    return i18n.t('label_collab_nick_usage')
                old = session.name
                session.name = arg[:24]
                self.announce(i18n.t('label_collab_nick', old=old, new=session.name))
                return ""
            if cmd in ("quit", "exit"):
                return None
            return i18n.t('label_collab_unknown')

    # host-console entry point (returns display text, never raises)
    def host_command(self, sub, arg):
        with self._cmd_lock:
            if sub == "status":
                return i18n.t('label_collab_host_status',
                              users=self._operator_count(),
                              alive=self.swarm.alive_count(),
                              total=self.swarm.total_count(),
                              port=self.bound_port or self.port)
            if sub in ("users", "who"):
                return self._render_who()
            if sub == "list":
                return self._render_list()
            if sub == "say" and arg:
                sent = self.swarm.say(arg, "alive")
                self.announce(i18n.t('label_collab_say', name="host", count=sent, text=arg))
                return i18n.t('label_swarm_say_sent', count=sent, text=arg)
            if sub == "add" and arg.isdigit():
                launched = self.swarm.add_bots(int(arg))
                self.announce(i18n.t('label_collab_add', name="host", count=len(launched),
                                     alive=self.swarm.alive_count(), total=self.swarm.total_count()))
                return i18n.t('label_collab_add', name="host", count=len(launched),
                              alive=self.swarm.alive_count(), total=self.swarm.total_count())
            if sub == "kick":
                selector = arg or "all"
                removed = self.swarm.kick(selector)
                self.announce(i18n.t('label_collab_kick', name="host", selector=selector, count=removed))
                return i18n.t('label_collab_kick', name="host", selector=selector, count=removed)
            return i18n.t('label_collab_host_usage')

    # ---- renderers --------------------------------------------------------
    def _operator_count(self):
        with self._sessions_lock:
            return len(self.sessions)

    def _render_help(self):
        return (
            "--- MBC-2.0 shared swarm console ---\n"
            "  status              bots alive/total\n"
            "  list                enumerate every bot\n"
            "  who                 connected operators\n"
            "  say <text>          broadcast to all alive bots\n"
            "  msg <sel> <text>    message one bot / prefix / index / all\n"
            "  add <n>             launch n more bots (live)\n"
            "  kick <sel|all>      disconnect matched bots\n"
            "  nick <name>         change your operator name\n"
            "  help                this help\n"
            "  quit                leave the shared console"
        )

    def _render_list(self):
        rows = self.swarm.list_bots()
        if not rows:
            return i18n.t('label_collab_list_empty')
        lines = [i18n.t('label_collab_list_header', total=len(rows),
                        alive=sum(1 for r in rows if r['alive']))]
        for r in rows[:200]:
            state = "ON " if r["alive"] else "off"
            lines.append(f"  #{r['index']:<4} {r['name']:<16} [{state}]")
        if len(rows) > 200:
            lines.append(f"  ... {len(rows) - 200} more")
        return "\n".join(lines)

    def _render_who(self):
        with self._sessions_lock:
            sessions = list(self.sessions)
        if not sessions:
            return i18n.t('label_collab_who_empty')
        lines = [i18n.t('label_collab_who_header', count=len(sessions))]
        for s in sessions:
            mins = int((time.time() - s.joined) // 60)
            lines.append(f"  {s.name:<24} {s.addr[0]}:{s.addr[1]}  ({mins}m)")
        return "\n".join(lines)

    def _status_to(self, session):
        session.send(i18n.t('label_swarm_status', alive=self.swarm.alive_count(), total=self.swarm.total_count()))
