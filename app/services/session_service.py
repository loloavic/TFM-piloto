"""Sesiones efímeras de un único proceso, con credenciales y borrado real."""
from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
from secrets import compare_digest, token_urlsafe
from threading import Event, RLock, Thread
from time import monotonic
from typing import Callable


class SesionNoAutorizada(Exception):
    pass


class CapacidadSesionesAgotada(Exception):
    pass


@dataclass
class Sesion:
    digest: bytes
    expires_at: float


class SessionStore:
    def __init__(self, delete_thread: Callable[[str], None], ttl: float, maximum: int,
                 clock: Callable[[], float] = monotonic):
        self.delete_thread = delete_thread
        self.ttl, self.maximum, self.clock = ttl, maximum, clock
        self.sessions: dict[str, Sesion] = {}
        # Serializa autorización, ejecución y borrado: no resucita un hilo eliminado.
        self.lock = RLock()
        self.stop = Event()
        self.worker: Thread | None = None

    def _delete(self, session_id: str) -> None:
        self.delete_thread(session_id)
        self.sessions.pop(session_id, None)

    def cleanup(self) -> None:
        with self.lock:
            now = self.clock()
            for sid, session in list(self.sessions.items()):
                if session.expires_at <= now:
                    self._delete(sid)

    def _authorize(self, sid: str, token: str | None) -> None:
        session = self.sessions.get(sid)
        if not session or not token or not compare_digest(
            session.digest, sha256(token.encode()).digest()
        ):
            raise SesionNoAutorizada('Sesión no disponible o credencial inválida')

    @contextmanager
    def access(self, sid: str, token: str | None):
        with self.lock:
            self.cleanup()
            if sid in self.sessions:
                self._authorize(sid, token)
                issued = token
            else:
                if token:
                    raise SesionNoAutorizada('Sesión no disponible o credencial inválida')
                if len(self.sessions) >= self.maximum:
                    raise CapacidadSesionesAgotada('Capacidad de sesiones agotada')
                issued = token_urlsafe(32)
                self.sessions[sid] = Sesion(sha256(issued.encode()).digest(), self.clock() + self.ttl)
            try:
                yield issued
            except Exception:
                # Un fallo puede haber creado checkpoints parciales. No conservarlos.
                self._delete(sid)
                raise
            finally:
                self.cleanup()

    def delete(self, sid: str, token: str | None) -> None:
        with self.lock:
            self.cleanup()
            self._authorize(sid, token)
            self._delete(sid)

    def start(self, interval: float) -> None:
        with self.lock:
            if self.worker and self.worker.is_alive():
                return
            self.stop.clear()
            def sweep():
                while not self.stop.wait(interval):
                    self.cleanup()
            self.worker = Thread(target=sweep, daemon=True, name='session-retention')
            self.worker.start()

    def close(self) -> None:
        self.stop.set()
        if self.worker:
            self.worker.join()
        with self.lock:
            for sid in list(self.sessions):
                self._delete(sid)
