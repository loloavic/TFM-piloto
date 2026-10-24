"""Frontera ASGI de Gradio: cookie privada + namespace HMAC por navegador.

Cada hash suministrado por el navegador se transforma antes de que Gradio lo use.
Conocer el hash de otro cliente no permite seleccionar su estado. No depende de
que gr.State sea privado ni de ocultar nombres de endpoints.
"""
import hashlib
import hmac
import json
import secrets
from http.cookies import CookieError, SimpleCookie
from time import time
from threading import RLock
from urllib.parse import parse_qsl, urlencode

from starlette.responses import JSONResponse


class GradioOwnerMiddleware:
    COOKIE = 'tfm_gradio_owner'

    def __init__(self, app, ttl=1800, secure=False, clock=time):
        self.app, self.ttl, self.secure, self.clock = app, ttl, secure, clock
        self.queues = {}
        self.queue_lock = RLock()
        self.key = secrets.token_bytes(32)  # Efímera: reiniciar revoca cookies.

    def _sign(self, text):
        return hmac.new(self.key, text.encode(), hashlib.sha256).hexdigest()

    def _owner(self, scope):
        jar = SimpleCookie()
        try:
            jar.load(dict(scope['headers']).get(b'cookie', b'').decode('latin1'))
            token = jar[self.COOKIE].value
            nonce, expires, signature = token.split('.')
            payload = nonce + '.' + expires
            if int(expires) > self.clock() and hmac.compare_digest(signature, self._sign('cookie:' + payload)):
                return token
        except (KeyError, ValueError, CookieError):
            pass
        return None

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'websocket':
            await send({'type': 'websocket.close', 'code': 1008})
            return
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        path = scope['path']
        # El piloto no necesita exportar estado, archivos, streaming multimedia
        # ni API simple por event_id. Evitar rutas auxiliares fuera del namespace.
        blocked = ('/gradio_api/deep_link', '/gradio_api/file', '/file=',
                   '/gradio_api/call', '/gradio_api/stream', '/gradio_api/upload',
                   '/gradio_api/reset', '/gradio_api/cancel', '/monitoring',
                   '/gradio_api/profiling', '/gradio_api/vibe-')
        if any(path.startswith(prefix) for prefix in blocked):
            return await JSONResponse({'detail': 'Ruta no disponible'}, 403)(scope, receive, send)
        headers = dict(scope['headers'])
        origin = headers.get(b'origin')
        expected_origin = scope['scheme'] + '://' + headers.get(b'host', b'').decode('latin1')
        if scope['method'] not in ('GET', 'HEAD') and origin and origin.decode('latin1') != expected_origin:
            return await JSONResponse({'detail': 'Origen no autorizado'}, 403)(scope, receive, send)
        owner = self._owner(scope)
        method = scope['method']
        requires_owner = method not in ('GET', 'HEAD') or '/queue/data' in path or '/heartbeat/' in path
        if requires_owner and not owner:
            return await JSONResponse({'detail': 'Abra la interfaz para iniciar sesión'}, 403)(scope, receive, send)
        fresh = owner is None
        if fresh:
            payload = secrets.token_urlsafe(32) + '.' + str(int(self.clock()) + self.ttl)
            owner = payload + '.' + self._sign('cookie:' + payload)

        def namespace(value):
            if not isinstance(value, str) or not value or len(value) > 256:
                raise ValueError('Hash inválido')
            return self._sign('session:' + owner + ':' + value)

        forwarded = dict(scope)
        try:
            query = parse_qsl(scope.get('query_string', b'').decode(), keep_blank_values=True)
            forwarded['query_string'] = urlencode([
                (k, namespace(v) if k == 'session_hash' else v) for k, v in query
            ]).encode()
            if '/heartbeat/' in path:
                prefix, value = path.rsplit('/', 1)
                forwarded['path'] = prefix + '/' + namespace(value)
                forwarded['raw_path'] = forwarded['path'].encode()
            if method not in ('GET', 'HEAD'):
                # Esta interfaz solo expone eventos JSON de su grafo de componentes.
                allowed = ('/gradio_api/queue/join', '/gradio_api/run/', '/gradio_api/api/')
                if not any(path.startswith(prefix) for prefix in allowed):
                    raise ValueError('Evento no permitido')
                chunks, length = [], 0
                while True:
                    message = await receive()
                    if message['type'] != 'http.request':
                        raise ValueError('Petición incompleta')
                    chunk = message.get('body', b'')
                    length += len(chunk)
                    if length > 65536:
                        raise ValueError('Petición demasiado grande')
                    chunks.append(chunk)
                    if not message.get('more_body'):
                        break
                body = json.loads(b''.join(chunks))
                body['session_hash'] = namespace(body.get('session_hash'))
                encoded = json.dumps(body).encode()
                forwarded['headers'] = [(k, v) for k, v in scope['headers'] if k != b'content-length']
                forwarded['headers'].append((b'content-length', str(len(encoded)).encode()))
                async def replay():
                    return {'type': 'http.request', 'body': encoded, 'more_body': False}
                receive = replay
        except (ValueError, TypeError, AttributeError, UnicodeError):
            return await JSONResponse({'detail': 'Evento de sesión inválido'}, 400)(scope, receive, send)

        # No dejar que una lectura SSE sin cola llegue a la excepción tardía
        # de Gradio (respuesta ya iniciada). Ledger de hashes, sin texto/tokens.
        queue_hash = None
        if path.rstrip('/') == '/gradio_api/queue/join':
            queue_hash = body['session_hash']
        stream_hash = None
        if path.rstrip('/') == '/gradio_api/queue/data':
            stream_hash = dict(parse_qsl(forwarded['query_string'].decode())).get('session_hash')
        with self.queue_lock:
            self.queues = {k: v for k, v in self.queues.items() if v > self.clock()}
            if stream_hash is not None and stream_hash not in self.queues:
                return_denied = True
            else:
                return_denied = False
            queue_full = queue_hash is not None and queue_hash not in self.queues and len(self.queues) >= 1024
        if return_denied:
            return await JSONResponse({'detail': 'Cola no disponible'}, 403)(scope, receive, send)
        if queue_full:
            return await JSONResponse({'detail': 'Capacidad de cola agotada'}, 503)(scope, receive, send)

        async def protected_send(message):
            if message['type'] == 'http.response.start':
                if queue_hash and 200 <= message['status'] < 300:
                    with self.queue_lock:
                        self.queues[queue_hash] = min(self.clock() + self.ttl, int(owner.split('.')[1]))
                message['headers'] = list(message.get('headers', []))
                message['headers'].append((b'cache-control', b'no-store'))
                if fresh:
                    cookie = f'{self.COOKIE}={owner}; Path=/; HttpOnly; SameSite=Strict; Max-Age={self.ttl}'
                    if self.secure:
                        cookie += '; Secure'
                    message['headers'].append((b'set-cookie', cookie.encode()))
            await send(message)
        await self.app(forwarded, receive, protected_send)
