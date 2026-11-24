"""SSRF guard (SPEC section 5.2): refuse URLs that point at internal addresses.

Server-Side Request Forgery: a user gives us a URL, and *our server* fetches it. Without this
check, `http://169.254.169.254/` (cloud metadata, often holding credentials), `http://localhost:8000`
or `http://10.0.0.5/admin` would let a customer read our private network through the crawler.

Checked for the start URL, every followed link and every redirect hop.
Known limitation: DNS rebinding (the name resolves to a public IP here and to a private IP when
the HTTP client connects a moment later). Closing it fully means pinning the checked IP in the
connection; documented in docs/NOTES.md.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit


class UnsafeURLError(ValueError):
    """The URL is not http(s), has no host, can't be resolved, or resolves to an internal IP."""


def _resolve(host: str, port: int) -> list[str]:
    """All IP addresses the host resolves to. Separate function so tests can fake DNS."""
    infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    return [str(info[4][0]) for info in infos]


def is_public_ip(raw: str) -> bool:
    ip = ipaddress.ip_address(raw.split("%", 1)[0])  # drop an IPv6 zone id like "fe80::1%eth0"
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped  # "::ffff:127.0.0.1" is really 127.0.0.1
    # is_global is False for private, loopback, link-local, reserved, unspecified and shared
    # (100.64/10) ranges. Some multicast ranges count as "global", so exclude multicast explicitly.
    return ip.is_global and not ip.is_multicast


def assert_public_url(url: str) -> None:
    """Raise UnsafeURLError unless *every* address the URL's host resolves to is public."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise UnsafeURLError(f"only http(s) URLs are allowed, got {parts.scheme or 'none'!r}")
    host = parts.hostname
    if not host:
        raise UnsafeURLError("URL has no host")

    try:
        port = parts.port or (443 if parts.scheme == "https" else 80)
        addresses = _resolve(host, port)
    except (socket.gaierror, UnicodeError, ValueError) as exc:
        raise UnsafeURLError(f"cannot resolve host {host!r}") from exc

    # All, not any: an attacker's DNS can return one public and one private record.
    if not addresses or not all(is_public_ip(a) for a in addresses):
        raise UnsafeURLError(f"host {host!r} resolves to an internal address")
