from __future__ import annotations

import socket

import pytest

from app.ingest import ssrf
from app.ingest.ssrf import UnsafeURLError, assert_public_url


@pytest.fixture
def fake_dns(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[str]]:
    """Map host -> IPs. IP literals resolve to themselves; unknown hosts fail like real DNS."""
    table: dict[str, list[str]] = {}

    def resolve(host: str, _port: int) -> list[str]:
        if host in table:
            return table[host]
        try:
            return [str(ssrf.ipaddress.ip_address(host))]
        except ValueError:
            raise socket.gaierror("unknown host") from None

    monkeypatch.setattr(ssrf, "_resolve", resolve)
    return table


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://127.0.0.1:8000/api/health",
        "http://localhost/",
        "http://10.0.0.5/admin",
        "http://172.16.0.1/",
        "http://192.168.1.1/",
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata endpoint
        "http://0.0.0.0/",
        "http://100.64.0.1/",  # carrier-grade NAT, not public
        "http://224.0.0.1/",  # multicast
        "http://[::1]/",
        "http://[::ffff:127.0.0.1]/",  # IPv4-mapped loopback
        "http://[fe80::1]/",  # IPv6 link-local
        "http://[fc00::1]/",  # IPv6 unique local (private)
    ],
)
def test_internal_addresses_are_refused(fake_dns: dict[str, list[str]], url: str) -> None:
    fake_dns["localhost"] = ["127.0.0.1"]
    with pytest.raises(UnsafeURLError):
        assert_public_url(url)


@pytest.mark.parametrize(
    "url", ["ftp://example.com/", "file:///etc/passwd", "gopher://example.com/", "http:///nohost"]
)
def test_non_http_or_hostless_urls_are_refused(fake_dns: dict[str, list[str]], url: str) -> None:
    with pytest.raises(UnsafeURLError):
        assert_public_url(url)


def test_public_host_is_allowed(fake_dns: dict[str, list[str]]) -> None:
    fake_dns["docs.example.com"] = ["93.184.216.34", "2606:2800:220:1:248:1893:25c8:1946"]
    assert_public_url("https://docs.example.com/getting-started")  # no exception


def test_one_private_record_is_enough_to_refuse(fake_dns: dict[str, list[str]]) -> None:
    fake_dns["sneaky.example.com"] = ["93.184.216.34", "10.0.0.5"]
    with pytest.raises(UnsafeURLError):
        assert_public_url("https://sneaky.example.com/")


def test_public_name_pointing_inside_is_refused(fake_dns: dict[str, list[str]]) -> None:
    fake_dns["internal.example.com"] = ["192.168.0.10"]
    with pytest.raises(UnsafeURLError):
        assert_public_url("https://internal.example.com/")


def test_unresolvable_host_is_refused(fake_dns: dict[str, list[str]]) -> None:
    with pytest.raises(UnsafeURLError, match="cannot resolve"):
        assert_public_url("https://does-not-exist.invalid/")
