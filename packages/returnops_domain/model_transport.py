"""A1.06 showcase model port and its one chat-completions transport.

FR-002; NFR-003/007/008/009; docs/44. The dialect is the chat-completions JSON
dialect used by common model gateways. urllib only: the runtime image has no
HTTP client dependency. The base URL is https without userinfo, query or
fragment; plain http is accepted only for 127.0.0.1 when a test passes
allow_insecure_loopback=True, or for an RFC 1918 IPv4 address with an explicit
port when allow_private_http=True (the course proxy at a 10.x address is
reachable only through the university VPN, which carries the traffic). Authorization is an unredirected header and every
3xx is a REDIRECT failure. One total deadline covers connect and read, and the
response body is capped at 256 KiB. No system proxy is used unless proxy_url is
given. Every failure is one closed code, raised without the request, response,
key or original exception chain. Usage (input/output tokens) is required.
unwrap_reply tolerates exactly one leading <think>...</think> block and one
surrounding ```json or ``` fence around the model's text; nothing else.
"""
from __future__ import annotations
from base64 import b64encode
from dataclasses import dataclass, field
from ipaddress import IPv4Address, ip_network
import json
import ssl
from threading import Event, Lock, Thread
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, ProxyHandler, Request, build_opener
from pydantic import SecretStr

DIALECT = 'chat-completions'
USER_AGENT = 'returnops-au-coordinator/1'
MAX_DEADLINE_SECONDS = 50
FAILURE_CODES = frozenset({'TRANSPORT', 'TIMEOUT', 'REDIRECT', 'HTTP_4XX', 'HTTP_429', 'HTTP_5XX',
                           'MALFORMED', 'NO_USAGE', 'TOO_LARGE', 'BUDGET'})
TRANSIENT_CODES = frozenset({'TRANSPORT', 'TIMEOUT', 'HTTP_429', 'HTTP_5XX'})
IMAGE_MEDIA_TYPES = frozenset({'image/jpeg', 'image/png'})
MAX_RESPONSE_BYTES = 256 * 1024
MAX_TOKENS_VALUE = 9007199254740991
PRIVATE_IPV4_NETWORKS = tuple(ip_network(block) for block in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))


class ModelTransportError(Exception):
    """A closed failure code only; never request/response text or the key."""
    def __init__(self, code):
        self.code = code if code in FAILURE_CODES else 'TRANSPORT'
        super().__init__(self.code)


@dataclass(frozen=True)
class ModelInvocation:
    """Only the fixed role instructions and the allow-listed JSON input reach a transport.

    images (C3, 1 November 2026): (media type, bytes) pairs, JPEG or PNG only, sent after
    the JSON; empty for every text-only call.
    """
    system_prompt: str = field(repr=False)
    input_json: str = field(repr=False)
    prompt_version: str
    provider_id: str
    model_id: str
    images: tuple = field(default=(), repr=False)


@dataclass(frozen=True)
class ModelReply:
    """The adapter supplies usage; model-generated content is untrusted text."""
    content: str = field(repr=False)
    input_tokens: int
    output_tokens: int


def _plain(value, limit):
    return type(value) is str and 1 <= len(value) <= limit and value.isascii() and value.isprintable() and not any(c.isspace() for c in value)


def _private_ipv4(hostname):
    try:
        address = IPv4Address(hostname)
    except ValueError:
        return False
    return any(address in block for block in PRIVATE_IPV4_NETWORKS)


def validate_base_url(raw, *, allow_insecure_loopback=False, allow_private_http=False):
    """Return the normalized base URL or raise ValueError without echoing it."""
    failed = False
    try:
        if not _plain(raw, 2048) or '?' in raw or '#' in raw or '@' in raw:
            raise ValueError
        parts = urlsplit(raw)
        port = parts.port
        if parts.username is not None or parts.password is not None or parts.query or parts.fragment or not parts.hostname:
            raise ValueError
        if parts.scheme == 'https':
            pass
        elif parts.scheme != 'http' or port is None:
            raise ValueError
        elif allow_insecure_loopback is True and parts.hostname == '127.0.0.1':
            pass
        elif not (allow_private_http is True and _private_ipv4(parts.hostname)):
            raise ValueError
    except (ValueError, TypeError):
        failed = True
    if failed:
        raise ValueError('The model base URL must be https without credentials, query or fragment.') from None
    return raw.rstrip('/')


def validate_proxy_url(raw):
    failed = False
    try:
        if not _plain(raw, 2048) or '?' in raw or '#' in raw or '@' in raw:
            raise ValueError
        parts = urlsplit(raw)
        parts.port
        if (parts.scheme not in {'http', 'https'} or not parts.hostname or parts.path not in {'', '/'}
                or parts.username is not None or parts.query or parts.fragment):
            raise ValueError
    except (ValueError, TypeError):
        failed = True
    if failed:
        raise ValueError('The model proxy URL must be http(s)://host:port without credentials.') from None
    return raw


def unwrap_reply(text):
    """Strip at most one leading <think>...</think> block, then at most one
    surrounding ```json / ``` fence. Any other wrapping is left for the JSON
    parser to reject (MALFORMED_JSON); the content itself is never edited."""
    value = text.strip()
    if value.startswith('<think>'):
        end = value.find('</think>')
        if end < 0:
            return value
        value = value[end + len('</think>'):].strip()
    if value.startswith('```') and value.endswith('```') and len(value) >= 6:
        first, newline, rest = value.partition('\n')
        if newline and first.strip() in {'```', '```json'}:
            value = rest[:-3].strip()
    return value


class _RefuseRedirect(HTTPRedirectHandler):
    """A redirect is never followed; the default handler then raises the 3xx."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _status_code(status):
    if 300 <= status <= 399: return 'REDIRECT'
    if status == 429: return 'HTTP_429'
    if 400 <= status <= 499: return 'HTTP_4XX'
    if 500 <= status <= 599: return 'HTTP_5XX'
    return 'TRANSPORT'


def _classify(error):
    if isinstance(error, ModelTransportError): return error.code
    if isinstance(error, HTTPError):
        try: error.close()
        except Exception: pass
        return _status_code(error.code) if type(error.code) is int else 'TRANSPORT'
    if isinstance(error, TimeoutError): return 'TIMEOUT'
    if isinstance(error, URLError):
        return 'TIMEOUT' if isinstance(error.reason, TimeoutError) else 'TRANSPORT'
    return 'TRANSPORT'


def parse_chat_completion(raw):
    """Chat-completions shape: choices[0].message.content plus usage tokens."""
    def invalid_constant(_): raise ValueError
    code = None
    try:
        document = json.loads(raw.decode('utf-8'), parse_constant=invalid_constant)
        choice = document['choices'][0]
        content = choice['message']['content']
        if type(document) is not dict or type(choice) is not dict or type(content) is not str or not content.strip():
            raise ValueError
    except (UnicodeError, ValueError, RecursionError, KeyError, IndexError, TypeError):
        code = 'MALFORMED'
    if code is not None:
        raise ModelTransportError(code) from None
    usage = document.get('usage')
    tokens = [usage.get(name) for name in ('prompt_tokens', 'completion_tokens')] if type(usage) is dict else [None, None]
    if any(type(value) is not int or not 0 <= value <= MAX_TOKENS_VALUE for value in tokens):
        raise ModelTransportError('NO_USAGE')
    return ModelReply(content, tokens[0], tokens[1])


class ChatCompletionsTransport:
    """Callable ModelInvocation -> ModelReply; one POST to {base_url}/chat/completions."""
    def __init__(self, base_url, api_key, model_id, *, deadline_seconds=20, proxy_url=None,
                 allow_insecure_loopback=False, allow_private_http=False, urlopen=None):
        if type(api_key) is not SecretStr or not _plain(api_key.get_secret_value(), 512):
            raise ValueError('The model API key must be a non-empty secret without whitespace.')
        if type(model_id) is not str or not 1 <= len(model_id) <= 120 or not model_id.isascii() or not model_id.isprintable():
            raise ValueError('The model ID must be 1-120 printable ASCII characters.')
        if type(deadline_seconds) not in (int, float) or not 0 < deadline_seconds <= MAX_DEADLINE_SECONDS:
            raise ValueError('The model deadline must be greater than 0 and at most 50 seconds.')
        self._endpoint = validate_base_url(base_url, allow_insecure_loopback=allow_insecure_loopback,
                                           allow_private_http=allow_private_http) + '/chat/completions'
        self._key = api_key
        self.model_id, self.deadline_seconds = model_id, deadline_seconds
        if urlopen is None:
            proxies = {} if proxy_url is None else {'http': validate_proxy_url(proxy_url), 'https': proxy_url}
            urlopen = build_opener(ProxyHandler(proxies), _RefuseRedirect(),
                                   HTTPSHandler(context=ssl.create_default_context())).open
        if not callable(urlopen):
            raise ValueError('The model transport opener must be callable.')
        self._urlopen = urlopen

    def __repr__(self):
        return 'ChatCompletionsTransport(dialect=' + repr(DIALECT) + ', model_id=' + repr(self.model_id) + ')'

    def _request(self, invocation):
        content = invocation.input_json
        if invocation.images:
            # C3 (1 November 2026): the photos follow the JSON as data URLs.
            content = [{'type': 'text', 'text': invocation.input_json}] + [
                {'type': 'image_url', 'image_url': {'url': 'data:' + media + ';base64,' + b64encode(data).decode('ascii')}}
                for media, data in invocation.images]
        body = json.dumps({'model': self.model_id, 'temperature': 0, 'messages': [
            {'role': 'system', 'content': invocation.system_prompt},
            {'role': 'user', 'content': content}]}, ensure_ascii=True).encode('ascii')
        request = Request(self._endpoint, data=body, method='POST')
        request.add_header('Content-Type', 'application/json')
        request.add_header('Accept', 'application/json')
        request.add_header('User-Agent', USER_AGENT)
        request.add_unredirected_header('Authorization', 'Bearer ' + self._key.get_secret_value())
        return request

    def _exchange(self, request, deadline):
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise ModelTransportError('TIMEOUT')
        response = self._urlopen(request, timeout=remaining)
        try:
            status = getattr(response, 'status', None)
            if type(status) is not int:
                raise ModelTransportError('TRANSPORT')
            if status != 200:
                raise ModelTransportError(_status_code(status))
            length = response.headers.get('Content-Length') if response.headers is not None else None
            if length is not None and length.strip().isdigit() and int(length) > MAX_RESPONSE_BYTES:
                raise ModelTransportError('TOO_LARGE')
            chunks, total = [], 0
            while True:
                if monotonic() >= deadline:
                    raise ModelTransportError('TIMEOUT')
                chunk = response.read(min(65536, MAX_RESPONSE_BYTES + 1 - total))
                if not chunk:
                    break
                chunks.append(chunk); total += len(chunk)
                if total > MAX_RESPONSE_BYTES:
                    raise ModelTransportError('TOO_LARGE')
            return b''.join(chunks)
        finally:
            response.close()

    def __call__(self, invocation):
        if type(invocation) is not ModelInvocation or invocation.model_id != self.model_id:
            raise ValueError('The invocation does not match this transport.')
        if type(invocation.images) is not tuple or any(
                type(item) is not tuple or len(item) != 2 or item[0] not in IMAGE_MEDIA_TYPES
                or type(item[1]) is not bytes or not item[1] for item in invocation.images):
            raise ValueError('Images must be (JPEG or PNG media type, bytes) pairs.')
        request = self._request(invocation)
        deadline = monotonic() + self.deadline_seconds
        outcome, done = {}, Event()

        def exchange():
            try:
                outcome['raw'] = self._exchange(request, deadline)
            except BaseException as error:
                outcome['code'] = _classify(error)
            finally:
                done.set()
        # The worker thread bounds connect+read by one total deadline; a stalled
        # socket is abandoned to its own (same) timeout, never awaited longer.
        Thread(target=exchange, name='returnops-model-call', daemon=True).start()
        finished = done.wait(max(0.0, deadline - monotonic()))
        request = None
        code = outcome.get('code', 'TRANSPORT') if 'raw' not in outcome else None
        if not finished:
            code = 'TIMEOUT'
        if code is not None:
            raise ModelTransportError(code) from None
        return parse_chat_completion(outcome['raw'])


class BudgetedTransport:
    """At most `max_calls` model calls (retries included) in this process (31 October 2026).

    A public deployment must not let strangers spend the key's quota without bound. Over
    budget, a call fails closed with BUDGET before anything is sent, and BUDGET is not a
    transient code, so it is not retried.
    """
    def __init__(self, inner, max_calls):
        if type(max_calls) is not int or max_calls < 1:
            raise ValueError('max_calls must be a positive integer')
        self.inner, self.remaining = inner, max_calls
        self._lock = Lock()

    def __call__(self, invocation):
        with self._lock:
            if self.remaining <= 0:
                raise ModelTransportError('BUDGET')
            self.remaining -= 1
        return self.inner(invocation)
