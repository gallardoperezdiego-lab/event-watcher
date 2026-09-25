"""
Event Watcher - Safe outbound HTTP.

The app only talks to public websites the user chose. This module enforces that:
  * only http:// and https:// URLs, without embedded usernames/passwords;
  * the host must resolve exclusively to public internet addresses. Loopback, private
    LAN, link-local (cloud metadata), carrier-grade NAT, multicast and reserved ranges
    are refused, so a watcher can never be used to probe the owner's router, NAS or
    this app's own local API;
  * the address that was checked is the one actually connected to (no DNS re-binding);
  * every redirect hop is re-validated, at most 5 hops;
  * responses are capped in size and the timeout covers the whole download.
"""

from __future__ import annotations

import http.client
import ipaddress
import socket
import ssl
import time
import urllib.error
import urllib.request
from typing import Optional, Tuple
from urllib.parse import urlsplit

MAX_RESPONSE_BYTES = 5 * 1024 * 1024
MAX_REDIRECTS = 5
BLOCKED_HOSTNAMES = {"localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback"}

_NAT64 = ipaddress.ip_network("64:ff9b::/96")
_CGNAT = ipaddress.ip_network("100.64.0.0/10")


class UnsafeURLError(ValueError):
    """The URL is malformed or points somewhere the app must not connect to."""


def is_public_ip(ip_text: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_text.split("%", 1)[0])
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped:
            return is_public_ip(str(ip.ipv4_mapped))
        if ip in _NAT64:
            return is_public_ip(str(ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)))
        if ip.sixtofour:
            return is_public_ip(str(ip.sixtofour))
    if isinstance(ip, ipaddress.IPv4Address) and ip in _CGNAT:
        return False
    return ip.is_global and not ip.is_multicast


def validate_url(url: str) -> str:
    """Syntax-level validation. Returns the normalised URL or raises UnsafeURLError."""
    if not url or len(url) > 2048:
        raise UnsafeURLError("Please enter a web address (URL).")
    if any(c in url for c in "\r\n\t ") :
        raise UnsafeURLError("The web address must not contain spaces or line breaks.")
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        raise UnsafeURLError("That web address is not valid.")
    if parts.scheme not in ("http", "https"):
        raise UnsafeURLError("Only web addresses starting with http:// or https:// can be monitored.")
    if not parts.hostname:
        raise UnsafeURLError("The web address is missing a website name.")
    if parts.username or parts.password:
        raise UnsafeURLError("Web addresses with a username or password are not allowed.")
    host = parts.hostname.rstrip(".").lower()
    if host in BLOCKED_HOSTNAMES or host.endswith(".localhost") or host.endswith(".local"):
        raise UnsafeURLError("Only public websites can be monitored (local network addresses are blocked).")
    try:
        ipaddress.ip_address(host)
        is_literal = True
    except ValueError:
        is_literal = False
    if is_literal and not is_public_ip(host):
        raise UnsafeURLError("Only public websites can be monitored (local network addresses are blocked).")
    if port is not None and not (0 < port < 65536):
        raise UnsafeURLError("The port in the web address is not valid.")
    return url


def resolve_public(host: str, port: int) -> Tuple[int, str]:
    """Resolve host and return (family, ip) only if *every* address is public."""
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise UnsafeURLError(f"Could not find the website '{host}' ({e.strerror or e}).")
    if not infos:
        raise UnsafeURLError(f"Could not find the website '{host}'.")
    for info in infos:
        if not is_public_ip(info[4][0]):
            raise UnsafeURLError(f"'{host}' points to a private or local network address and was blocked.")
    family, _, _, _, sockaddr = infos[0]
    return family, sockaddr[0]


def _open_socket(host: str, port: int, timeout: Optional[float], source_address) -> socket.socket:
    family, ip = resolve_public(host, port)
    sock = socket.socket(family, socket.SOCK_STREAM)
    try:
        if timeout is not None:
            sock.settimeout(timeout)
        if source_address:
            sock.bind(source_address)
        sock.connect((ip, port))
        return sock
    except OSError:
        sock.close()
        raise


class _GuardedHTTPConnection(http.client.HTTPConnection):
    def connect(self):
        self.sock = _open_socket(self.host, self.port, self.timeout, self.source_address)


class _GuardedHTTPSConnection(http.client.HTTPSConnection):
    def connect(self):
        sock = _open_socket(self.host, self.port, self.timeout, self.source_address)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi  # bundled in packaged builds; macOS Python often lacks system CAs

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


class _GuardedHTTPHandler(urllib.request.HTTPHandler):
    def http_open(self, req):
        return self.do_open(_GuardedHTTPConnection, req)


class _GuardedHTTPSHandler(urllib.request.HTTPSHandler):
    def __init__(self):
        super().__init__(context=_ssl_context())

    def https_open(self, req):
        return self.do_open(_GuardedHTTPSConnection, req, context=self._context)


class _GuardedRedirectHandler(urllib.request.HTTPRedirectHandler):
    max_redirections = MAX_REDIRECTS

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = urllib.request.OpenerDirector()
for _handler in (
    urllib.request.ProxyHandler({}),  # never route through env/system proxies
    urllib.request.UnknownHandler(),
    _GuardedHTTPHandler(),
    _GuardedHTTPSHandler(),
    urllib.request.HTTPDefaultErrorHandler(),
    _GuardedRedirectHandler(),
    urllib.request.HTTPErrorProcessor(),
):
    _opener.add_handler(_handler)


class FetchResult:
    __slots__ = ("ok", "status", "text", "response_time_ms", "error", "final_url")

    def __init__(self, ok, status, text, response_time_ms, error=None, final_url=None):
        self.ok = ok
        self.status = status
        self.text = text
        self.response_time_ms = response_time_ms
        self.error = error
        self.final_url = final_url


def safe_fetch(url: str, user_agent: str, timeout: float = 15) -> FetchResult:
    start = time.monotonic()
    deadline = start + timeout

    def elapsed_ms() -> int:
        return int((time.monotonic() - start) * 1000)

    try:
        validate_url(url)
        req = urllib.request.Request(url, headers={
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml,text/xml,application/rss+xml,"
                      "application/atom+xml,text/calendar,*/*;q=0.8",
            "Accept-Language": "en-GB,en;q=0.9",
            "Accept-Encoding": "identity",
        })
        with _opener.open(req, timeout=timeout) as resp:
            chunks, size = [], 0
            while True:
                if time.monotonic() > deadline:
                    return FetchResult(False, resp.status, "", elapsed_ms(),
                                       f"Request timed out after {int(timeout)}s")
                chunk = resp.read(64 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_RESPONSE_BYTES:
                    return FetchResult(False, resp.status, "", elapsed_ms(),
                                       f"Page is larger than {MAX_RESPONSE_BYTES // (1024 * 1024)} MB and was skipped")
                chunks.append(chunk)
            charset = resp.headers.get_content_charset() or "utf-8"
            try:
                text = b"".join(chunks).decode(charset, errors="replace")
            except LookupError:
                text = b"".join(chunks).decode("utf-8", errors="replace")
            return FetchResult(True, resp.status, text, elapsed_ms(), None, resp.geturl())
    except UnsafeURLError as e:
        return FetchResult(False, None, "", elapsed_ms(), str(e))
    except urllib.error.HTTPError as e:
        return FetchResult(False, e.code, "", elapsed_ms(), f"HTTP {e.code}: {e.reason}")
    except urllib.error.URLError as e:
        reason = e.reason
        if isinstance(reason, UnsafeURLError):
            return FetchResult(False, None, "", elapsed_ms(), str(reason))
        if isinstance(reason, socket.timeout):
            return FetchResult(False, None, "", elapsed_ms(), f"Request timed out after {int(timeout)}s")
        return FetchResult(False, None, "", elapsed_ms(), f"Network error: {reason}")
    except (socket.timeout, TimeoutError):
        return FetchResult(False, None, "", elapsed_ms(), f"Request timed out after {int(timeout)}s")
    except (OSError, http.client.HTTPException, ValueError) as e:
        return FetchResult(False, None, "", elapsed_ms(), f"Network error: {e}")
