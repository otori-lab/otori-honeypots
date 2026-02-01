"""
Log Shipper - Envoie les logs du honeypot vers le monitoring.

Fonctionnalités:
- Enregistrement automatique auprès du monitoring au démarrage
- Tail du fichier de logs et envoi en temps réel
- Buffer disque pour robustesse (retry en cas d'échec)
- Conversion du format interne vers OtoriEventIn
"""

import json
import logging
import os
import socket
import threading
import time
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

# =========================
# CONFIG
# =========================
MONITORING_URL = os.environ.get("MONITORING_URL", "")
PROFILE_NAME = os.environ.get("PROFILE_NAME", "")
FAKE_HOSTNAME = os.environ.get("FAKE_HOSTNAME", "honeypot")

DATA_DIR = Path(os.environ.get("DATA_DIR", "/app/data"))
LOG_DIR = Path(os.environ.get("LOG_DIR", "logs"))

SENSOR_FILE = DATA_DIR / "sensor.json"
POSITION_FILE = DATA_DIR / "position.txt"
BUFFER_FILE = LOG_DIR / "buffer.jsonl"
LOG_FILE = LOG_DIR / "honeypot_sessions.jsonl"

RETRY_INTERVAL = 30  # seconds
SHIP_INTERVAL = 1  # seconds


def _get_local_ip() -> str:
    """Récupère l'IP locale de la machine."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class LogShipper:
    """Envoie les logs du honeypot vers le serveur monitoring."""

    def __init__(self):
        self.monitoring_url = MONITORING_URL.rstrip("/")
        self.sensor_id = None
        self.token = None
        self.running = False
        self._http = requests.Session()
        self._ship_thread = None
        self._retry_thread = None

    def is_enabled(self) -> bool:
        """Vérifie si le monitoring est configuré."""
        return bool(self.monitoring_url)

    def register(self) -> bool:
        """Enregistre le honeypot auprès du monitoring."""
        if not self.is_enabled():
            logger.info("Monitoring disabled (MONITORING_URL not set)")
            return False

        # Vérifier si déjà enregistré
        if SENSOR_FILE.exists():
            try:
                data = json.loads(SENSOR_FILE.read_text())
                self.sensor_id = data["sensor_id"]
                self.token = data.get("token")
                logger.info(f"Sensor already registered: {self.sensor_id}")
                return True
            except Exception as e:
                logger.warning(f"Failed to read sensor file: {e}")

        # Enregistrement
        try:
            resp = self._http.post(
                f"{self.monitoring_url}/register",
                json={
                    "hostname": FAKE_HOSTNAME,
                    "honeypot_type": "ia",
                    "ip": _get_local_ip(),
                    "profile_name": PROFILE_NAME or None,
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            self.sensor_id = data["sensor_id"]
            self.token = data.get("token")

            # Sauvegarder pour les prochains démarrages
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            SENSOR_FILE.write_text(json.dumps(data, indent=2))

            logger.info(f"Sensor registered: {self.sensor_id}")
            return True

        except requests.exceptions.ConnectionError:
            logger.error(f"Cannot connect to monitoring: {self.monitoring_url}")
            return False
        except requests.exceptions.Timeout:
            logger.error("Registration timeout")
            return False
        except Exception as e:
            logger.error(f"Registration failed: {e}")
            return False

    def _convert_event(self, raw: dict) -> dict | None:
        """Convertit un event interne vers le format OtoriEventIn."""
        event_type_map = {
            "session_start": "connect",
            "session_end": "closed",
            "command": "command",
            "login_success": "login_success",
            "login_failed": "login_failed",
        }

        raw_type = raw.get("type", "")
        event_type = event_type_map.get(raw_type)

        if not event_type:
            # Skip internal events like output, llm_success, etc.
            return None

        return {
            "timestamp": raw.get("ts", ""),
            "sensor": self.sensor_id,
            "honeypot_type": "ia",
            "session_id": raw.get("sid"),
            "src_ip": raw.get("ip"),
            "src_port": raw.get("port"),
            "event_type": event_type,
            "command": raw.get("cmd"),
            "username": raw.get("username"),
            "password": raw.get("password"),
            "duration_sec": raw.get("duration"),
        }

    def _ship_event(self, event: dict) -> bool:
        """Envoie un event au monitoring."""
        try:
            resp = self._http.post(
                f"{self.monitoring_url}/ingest",
                json=event,
                timeout=5,
            )
            return resp.status_code == 200
        except Exception as e:
            logger.debug(f"Ship failed: {e}")
            return False

    def _buffer_event(self, event: dict):
        """Écrit un event dans le buffer disque."""
        try:
            with BUFFER_FILE.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
        except Exception as e:
            logger.error(f"Buffer write failed: {e}")

    def _get_position(self) -> int:
        """Récupère la position de lecture sauvegardée."""
        try:
            if POSITION_FILE.exists():
                return int(POSITION_FILE.read_text().strip())
        except Exception:
            pass
        return 0

    def _save_position(self, pos: int):
        """Sauvegarde la position de lecture."""
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            POSITION_FILE.write_text(str(pos))
        except Exception as e:
            logger.error(f"Position save failed: {e}")

    def _ship_loop(self):
        """Thread principal: tail le fichier de logs et envoie les events."""
        position = self._get_position()
        logger.info(f"Starting ship loop from position {position}")

        while self.running:
            try:
                if not LOG_FILE.exists():
                    time.sleep(SHIP_INTERVAL)
                    continue

                with LOG_FILE.open("r", encoding="utf-8") as f:
                    f.seek(position)

                    for line in f:
                        if not self.running:
                            break

                        line = line.strip()
                        if not line:
                            continue

                        try:
                            raw = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        event = self._convert_event(raw)
                        if not event:
                            continue

                        if self._ship_event(event):
                            logger.debug(f"Shipped: {event.get('event_type')} sid={event.get('session_id')[:8]}")
                        else:
                            self._buffer_event(event)
                            logger.warning(f"Buffered: {event.get('event_type')}")

                    position = f.tell()
                    self._save_position(position)

            except Exception as e:
                logger.error(f"Ship loop error: {e}")

            time.sleep(SHIP_INTERVAL)

    def _retry_loop(self):
        """Thread de retry: relit le buffer et réessaie les events échoués."""
        while self.running:
            time.sleep(RETRY_INTERVAL)

            if not BUFFER_FILE.exists():
                continue

            try:
                # Lire le buffer
                with BUFFER_FILE.open("r", encoding="utf-8") as f:
                    lines = f.readlines()

                if not lines:
                    continue

                logger.info(f"Retrying {len(lines)} buffered events...")

                # Réessayer chaque event
                failed = []
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if not self._ship_event(event):
                        failed.append(line)

                # Réécrire les events échoués
                if failed:
                    with BUFFER_FILE.open("w", encoding="utf-8") as f:
                        f.write("\n".join(failed) + "\n")
                    logger.info(f"Retry: {len(lines) - len(failed)} success, {len(failed)} still buffered")
                else:
                    BUFFER_FILE.unlink(missing_ok=True)
                    logger.info(f"Retry: all {len(lines)} events shipped successfully")

            except Exception as e:
                logger.error(f"Retry loop error: {e}")

    def start(self):
        """Démarre les threads de shipping."""
        if not self.is_enabled():
            return

        if not self.sensor_id:
            if not self.register():
                logger.warning("Shipper not started (registration failed)")
                return

        self.running = True

        self._ship_thread = threading.Thread(target=self._ship_loop, daemon=True, name="log-shipper")
        self._ship_thread.start()

        self._retry_thread = threading.Thread(target=self._retry_loop, daemon=True, name="log-retry")
        self._retry_thread.start()

        logger.info("Log shipper started")

    def stop(self):
        """Arrête les threads."""
        self.running = False
        logger.info("Log shipper stopped")


# Singleton
_shipper = LogShipper()


def start_shipper():
    """Démarre le log shipper (appelé depuis honeypot_ssh.py)."""
    _shipper.start()


def stop_shipper():
    """Arrête le log shipper."""
    _shipper.stop()


def get_sensor_id() -> str | None:
    """Retourne le sensor_id si enregistré."""
    return _shipper.sensor_id
