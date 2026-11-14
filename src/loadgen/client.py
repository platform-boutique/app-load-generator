"""One simulated visitor: an HTTP client with its own cookie jar plus request helpers that check responses.

Every request goes through Step(): the status and the page markers are verified and a response that does not meet
them is reported to Locust as a failure with a short, constant message (so failures group in the summary).
Redirects are never followed by the HTTP library; a journey follows the ones it expects, and only to the same host.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from . import page

DEFAULT_TIMEOUT = 30.0  # seconds for connect plus read of one request (CODE-05)


def drop_secure_flag(jar) -> None:
    """Clear the `Secure` flag of every cookie in the jar so the cookies are sent back over plain http.

    The frontend marks its cookies Secure (right for production). Browsers still send them to http://localhost,
    but python-requests follows RFC 6265 strictly and drops them, which would make every request a new visitor
    with an empty cart. (A custom cookie policy does not help: requests copies the jar into a new one with the
    default policy before each request.) This is a test client against our own stack, so the flag is cleared.
    """
    for cookie in jar:
        cookie.secure = False


@dataclass
class Reply:
    """What a step returns: the HTTP status, the page text and the Location header (if any)."""

    status: int
    text: str
    location: str = ""
    ok: bool = True
    reasons: list[str] = field(default_factory=list)


class Visitor:
    """Wraps a Locust HttpSession (`client`) for one user. `host` is only used to refuse foreign redirects."""

    def __init__(self, client, host: str, timeout: float = DEFAULT_TIMEOUT) -> None:
        self.client = client
        self.host = host
        self.timeout = timeout

    def step(
        self,
        method: str,
        path: str,
        name: str | None = None,
        *,
        status: int | Iterable[int] = 200,
        has: Iterable[str] = (),
        lacks: Iterable[str] = (),
        data: dict[str, str] | None = None,
        location: Iterable[str] | None = None,
        no_leaks: bool = True,
    ) -> Reply:
        """Request `path`, check it, return Reply. `has`/`lacks` are page markers (case-insensitive);
        `location` is a set of allowed redirect targets (path prefixes) when the status is a redirect."""
        wanted = {status} if isinstance(status, int) else set(status)
        reasons: list[str] = []
        with self.client.request(
            method, path, name=name or path, data=data, allow_redirects=False, catch_response=True, timeout=self.timeout
        ) as resp:
            code = resp.status_code
            text = resp.text if code else ""
            loc = resp.headers.get("Location", "") if code else ""
            if code == 0:
                reasons.append("no response (connection error or timeout)")
            elif code not in wanted:
                reasons.append(f"HTTP {code}, expected {'/'.join(str(s) for s in sorted(wanted))}")
            else:
                reasons += self._check_page(text, has, lacks, no_leaks)
                if location is not None and code in (301, 302, 303, 307):
                    reasons += self._check_location(loc, location)
            if reasons:
                resp.failure("; ".join(reasons))
            else:
                resp.success()
        drop_secure_flag(self.client.cookies)
        return Reply(code, text, loc, not reasons, reasons)

    @staticmethod
    def _check_page(text: str, has: Iterable[str], lacks: Iterable[str], check_leaks: bool) -> list[str]:
        out = [f"missing marker {m!r}" for m in has if not page.contains(text, m)]
        out += [f"unexpected marker {m!r}" for m in lacks if page.contains(text, m)]
        if check_leaks and page.leaks_internals(text):
            out.append("page leaks internals (rpc error / stack trace / hash)")
        return out

    def _check_location(self, loc: str, allowed: Iterable[str]) -> list[str]:
        path = page.same_origin_path(self.host, loc)
        if path is None:
            return [f"redirect leaves the host: {loc!r}"]
        if not any(path == a or path.startswith(a + "?") or path.startswith(a + "/") for a in allowed):
            return [f"unexpected redirect target {path.split('?')[0]!r}"]
        return []

    def get(self, path: str, name: str | None = None, **kw) -> Reply:
        return self.step("GET", path, name, **kw)

    def post(self, path: str, data: dict[str, str], name: str | None = None, **kw) -> Reply:
        return self.step("POST", path, name, data=data, **kw)

    def follow(self, reply: Reply, name: str | None = None, **kw) -> Reply | None:
        """GET the Location of a redirect reply (same host only). None if there is nothing safe to follow."""
        path = page.same_origin_path(self.host, reply.location) if reply.location else None
        if path is None:
            return None
        return self.get(path, name, **kw)
