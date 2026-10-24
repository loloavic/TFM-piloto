"""Sesiones efímeras: registro breve y exclusión por hilo, no por servicio."""
from contextlib import contextmanager
from dataclasses import dataclass, field
from hashlib import sha256
from secrets import compare_digest, token_urlsafe
from threading import Event, Lock, RLock, Thread
from time import monotonic
from typing import Callable


class SesionNoAutorizada(Exception):
    pass


class SesionCaducada(Exception):
    pass


class SesionOcupada(Exception):
    pass


class CapacidadSesionesAgotada(Exception):
    pass


@dataclass
class Sesion:
    digest: bytes
    expires_at: float
    mutex: Lock = field(default_factory=Lock, repr=False)


class SessionStore:
    def __init__(self, delete_thread: Callable[[str], None], ttl: float, maximum: int,
                 clock: Callable[[], float] = monotonic, wait_seconds: float = 5):
        self.delete_thread = delete_thread
        self.ttl, self.maximum, self.clock = ttl, maximum, clock
        self.wait_seconds = wait_seconds
        self.sessions: dict[str, Sesion] = {}
        self.lock = RLock()  # Solo registro; nunca se mantiene durante inferencia/esperas.
        self.stop = Event()
        self.worker: Thread | None = None

    def _delete(self, sid: str, session: Sesion) -> None:
        # El llamador posee session.mutex. No permite crear otro hilo con el
        # mismo ID hasta haber eliminado los artefactos del anterior.
        with self.lock:
            if self.sessions.get(sid) is session:
                self.delete_thread(sid)
                del self.sessions[sid]

    def cleanup(self) -> None:
        with self.lock:
            expired = [(sid, s) for sid, s in self.sessions.items()
                       if s.expires_at <= self.clock()]
        for sid, session in expired:
            if session.mutex.acquire(blocking=False):
                try:
                    self._delete(sid, session)
                finally:
                    session.mutex.release()

    @staticmethod
    def _authorize(session: Sesion, token: str | None) -> None:
        if not token or not compare_digest(session.digest, sha256(token.encode()).digest()):
            raise SesionNoAutorizada('Sesión no disponible o credencial inválida')

    @contextmanager
    def access(self, sid: str, token: str | None):
        self.cleanup()
        with self.lock:
            session = self.sessions.get(sid)
            if session is None:
                if token:
                    raise SesionNoAutorizada('Sesión no disponible o credencial inválida')
                if len(self.sessions) >= self.maximum:
                    raise CapacidadSesionesAgotada('Capacidad de sesiones agotada')
                token = token_urlsafe(32)
                session = Sesion(sha256(token.encode()).digest(), self.clock() + self.ttl)
                self.sessions[sid] = session
            else:
                self._authorize(session, token)
        if not session.mutex.acquire(timeout=self.wait_seconds):
            raise SesionOcupada('Sesión ocupada')
        try:
            with self.lock:
                if self.sessions.get(sid) is not session or session.expires_at <= self.clock():
                    self._delete(sid, session)
                    raise SesionNoAutorizada('Sesión no disponible o credencial inválida')
            try:
                yield token
            except Exception:
                self._delete(sid, session)
                raise
            else:
                if session.expires_at <= self.clock():
                    self._delete(sid, session)
                    # Descarta el resultado: no devolver éxito con token inválido.
                    raise SesionCaducada('La sesión caducó durante la consulta')
        finally:
            session.mutex.release()
            self.cleanup()

    def delete(self, sid: str, token: str | None) -> None:
        self.cleanup()
        with self.lock:
            session = self.sessions.get(sid)
            if session is None:
                raise SesionNoAutorizada('Sesión no disponible o credencial inválida')
            self._authorize(session, token)
        if not session.mutex.acquire(timeout=self.wait_seconds):
            raise SesionOcupada('Sesión ocupada')
        try:
            with self.lock:
                if self.sessions.get(sid) is not session:
                    raise SesionNoAutorizada('Sesión no disponible o credencial inválida')
            self._delete(sid, session)
        finally:
            session.mutex.release()

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
            entries = list(self.sessions.items())
        for sid, session in entries:
            # Cierre ordenado: no borrar bajo una ejecución que podría reescribir.
            with session.mutex:
                self._delete(sid, session)
