from src import i18n
# MBC-2.0 (CREADDINSCART STUDIO)
# This module extends the 1.0 bot swarm with live scaling so a shared operator
# console can grow, shrink and target the swarm while it is running.
# Structure and the connection/auth logic originate from the upstream
# MinecraftBotClient project (CREADDINSCART STUDIO).

import random
import string
import threading

from src.network.connection_manager import ConnectionManager


class BotWorker:
    def __init__(self, index, name, address, version, protocol_id, settings, log_func, stop_event):
        self.index = index
        self.name = name
        self.address = address
        self.version = version
        self.protocol_id = protocol_id
        self.settings = settings
        self.log = log_func
        self.stop_event = stop_event
        self.connection = None
        self.connected = False
        self.joined_at = None

    def run(self):
        conn = ConnectionManager()
        self.connection = conn
        try:
            conn.connect(
                server_address=self.address,
                username=self.name,
                protocol_version=self.version,
                protocol_id=self.protocol_id,
                log_func=lambda message: None,
                on_disconnect=self._on_disconnect,
            )
        except Exception as e:
            self.log(i18n.t('label_bot_failed', name=self.name, err=str(e)))
            self.connected = False
            return

        self.connected = True
        self.joined_at = __import__('time').time()
        self.log(i18n.t('label_bot_joined', name=self.name))
        self.authenticate()

        while not self.stop_event.is_set():
            if not conn.is_alive():
                break
            if self.stop_event.wait(0.5):
                break

        self.connected = False
        try:
            conn.disconnect()
        except Exception:
            pass
        self.log(i18n.t('label_bot_left', name=self.name))

    def _on_disconnect(self):
        self.connected = False

    def authenticate(self):
        if not self.settings.get("bot_auth_enabled", False):
            return
        password = str(self.settings.get("bot_auth_password", "") or "")
        if not password:
            self.log(i18n.t('label_bot_auth_no_password', name=self.name))
            return

        delay = float(self.settings.get("bot_auth_delay", 1.5) or 0)
        if delay > 0 and self.stop_event.wait(delay):
            return

        mode = str(self.settings.get("bot_auth_mode", "register") or "register").lower()
        if mode not in ("register", "login", "both"):
            mode = "register"

        if mode in ("register", "both"):
            self.send_auth_command("bot_auth_register_command", "/register {password} {password}", password)
            if mode == "both":
                if self.stop_event.wait(1.0):
                    return
        if mode in ("login", "both"):
            self.send_auth_command("bot_auth_login_command", "/login {password}", password)

    def send_auth_command(self, key, default, password):
        template = str(self.settings.get(key, default) or default)
        command = template.replace("{password}", password)
        if not command.strip() or not self.connection:
            return
        try:
            self.connection.send_chat(command)
            self.log(i18n.t('label_bot_auth_sent', name=self.name, cmd=command))
        except Exception as e:
            self.log(i18n.t('label_bot_failed', name=self.name, err=str(e)))

    def send_chat(self, message):
        if not self.connected or not self.connection:
            return False
        try:
            self.connection.send_chat(message)
            return True
        except Exception:
            return False

    def is_alive(self):
        return bool(self.connected and self.connection and self.connection.is_alive())

    def tell(self, message):
        """Send a private /msg to this single bot (used by targeted swarm commands)."""
        return self.send_chat(message)

    def request_stop(self):
        """Ask this worker's loop to exit without killing the whole swarm."""
        # Each live worker shares the swarm stop_event; give it a personal flag.
        if not hasattr(self, "_solo_stop"):
            self._solo_stop = threading.Event()
            # Re-point the worker loop onto a per-worker event so kick() is isolated.
            self.stop_event = self._solo_stop
        self._solo_stop.set()
        self.disconnect()

    def disconnect(self):
        self.connected = False
        if self.connection:
            try:
                self.connection.disconnect()
            except Exception:
                pass


class BotSwarm:
    def __init__(self, settings, log_func):
        self.settings = settings
        self.log = log_func
        self.stop_event = threading.Event()
        self.workers = []
        self.threads = []
        self._lock = threading.RLock()
        self._next_index = 1
        self._used_names = set()
        self.protocol_id = None
        self.address = str(self.settings.get("server_address", "localhost:25565") or "localhost:25565")
        self.version = str(self.settings.get("minecraft_version", "1.8.9") or "1.8.9")

    # ---- launch -----------------------------------------------------------
    def start(self):
        count = int(self.settings.get("bot_count", 10) or 10)
        count = max(1, min(count, 500))
        self.protocol_id = self.detect_protocol()
        self.add_bots(count, announce=True)

    def add_bots(self, count, announce=False, delay=None):
        """Live-scale the swarm by `count` more bots. Returns the launched names."""
        count = max(0, min(int(count), 500))
        if count == 0:
            return []
        if self.protocol_id is None:
            self.protocol_id = self.detect_protocol()
        if delay is None:
            delay = float(self.settings.get("bot_join_delay", 0.5) or 0)

        names = self.make_names(count)
        if announce:
            self.log(i18n.t('label_swarm_target', count=len(names), addr=self.address))

        launched = []
        for i, name in enumerate(names):
            if self.stop_event.is_set():
                break
            with self._lock:
                index = self._next_index
                self._next_index += 1
            worker = BotWorker(index, name, self.address, self.version, self.protocol_id,
                               self.settings, self.log, self.stop_event)
            thread = threading.Thread(target=worker.run, daemon=True, name=f"mbc-bot-{name}")
            with self._lock:
                self.workers.append(worker)
                self.threads.append(thread)
            thread.start()
            launched.append(name)
            if delay > 0 and i < len(names) - 1:
                if self.stop_event.wait(delay):
                    break
        return launched

    def detect_protocol(self):
        probe = ConnectionManager()
        host, port, _ = probe.resolve_address(self.address)
        detected = probe.detect_protocol(host, int(port))
        if detected:
            protocol_id, name = detected
            self.log(i18n.t('label_protocol_detected', name=name or '?', pid=protocol_id))
            return protocol_id
        protocol_id, _ = ConnectionManager.resolve_protocol(self.version)
        self.log(i18n.t('label_protocol_fallback', ver=self.version, pid=protocol_id))
        return protocol_id

    def make_names(self, count):
        prefix = str(self.settings.get("bot_name_prefix", "Bot") or "Bot")
        digits = int(self.settings.get("bot_name_digits", 4) or 4)
        digits = max(2, min(6, digits))
        max_prefix = max(1, 16 - digits)
        prefix = prefix[:max_prefix]

        names = []
        guard = 0
        while len(names) < count and guard < count * 100:
            guard += 1
            name = prefix + ''.join(random.choices(string.digits, k=digits))
            if name in self._used_names:
                continue
            self._used_names.add(name)
            names.append(name)
        return names

    # ---- targeting (MBC-2.0) ---------------------------------------------
    def _match(self, selector):
        """Resolve a selector to a list of workers.
        selector: 'all' | int index | exact/prefix name | 'alive'."""
        sel = (str(selector).strip().lower()) if selector is not None else "all"
        with self._lock:
            workers = list(self.workers)
        if sel in ("", "all"):
            return workers
        if sel == "alive":
            return [w for w in workers if w.is_alive()]
        if sel.isdigit():
            idx = int(sel)
            return [w for w in workers if w.index == idx]
        # name match: exact or prefix
        exact = [w for w in workers if w.name.lower() == sel]
        if exact:
            return exact
        return [w for w in workers if w.name.lower().startswith(sel)]

    def list_bots(self):
        with self._lock:
            workers = list(self.workers)
        rows = []
        for w in workers:
            rows.append({
                "index": w.index,
                "name": w.name,
                "alive": w.is_alive(),
            })
        return rows

    def kick(self, selector):
        """Disconnect matched bots. Returns number kicked."""
        targets = self._match(selector)
        for w in targets:
            w.request_stop()
        with self._lock:
            self.workers = [w for w in self.workers if w not in targets]
        return len(targets)

    def say(self, message, selector="all"):
        sent = 0
        for worker in self._match(selector):
            if worker.send_chat(message):
                sent += 1
        return sent

    def say_to(self, selector, message):
        return self.say(message, selector)

    def alive_count(self):
        with self._lock:
            workers = list(self.workers)
        return sum(1 for worker in workers if worker.is_alive())

    def total_count(self):
        with self._lock:
            return len(self.workers)

    def stop(self):
        self.stop_event.set()
        with self._lock:
            workers = list(self.workers)
        for worker in workers:
            worker.disconnect()
        for thread in self.threads:
            thread.join(timeout=3)
