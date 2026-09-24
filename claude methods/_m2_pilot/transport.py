"""M2a R2 - transport-level controls, enforced on every actual HTTP attempt.

Why this exists
---------------
The pilot budget is measured in HTTP attempts, not symbol jobs: one raw
`stock_zh_a_daily` call issues TWO GETs (price history + amount series). Pacing applied
per symbol would therefore under-count by a factor of two and pace at half the intended
rate. Every attempt goes through `PacedTransport.get`, so the counter and the pacing see
the same events the network does.

Deliberate choices
------------------
* Redirects are DISABLED. A followed redirect is a second HTTP attempt that neither the
  ceiling nor the pacing would otherwise see, so a 3xx is surfaced as a failure instead.
* Library-level retries are DISABLED and asserted. urllib3's default Retry would issue
  hidden attempts underneath us; retries here are explicit, bounded and counted.
* 403/429 stop the ENTIRE run immediately and are never retried. Backing off and trying
  again is how a soft rate-limit becomes a ban.
* Timeouts are finite and mandatory on every attempt; there is no code path that can
  wait forever.
* The clock and the sleeper are injected, so the tests exercise real pacing decisions
  without real waiting, and no test can accidentally reach the network.

This module performs NO live requests. `LiveTransport` is defined for completeness but
refuses to run unless explicitly constructed with `armed=True`, which nothing in M2a does.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

CONNECT_TIMEOUT = 10.0
READ_TIMEOUT = 30.0
DEFAULT_CEILING = 306
DEFAULT_MIN_INTERVAL = 1.5
MAX_ATTEMPTS_PER_JOB = 3
BACKOFF = (2.0, 8.0, 32.0)

RETRYABLE_STATUS = frozenset({500, 502, 503, 504})
STOP_STATUS = frozenset({403, 429})

#: ONLY these exception types are transient I/O. Everything else - a
#: ValueError from a broken parser, a KeyError, an assertion - is a bug in us
#: or in the response, and repeating the request cannot fix it. The previous
#: blanket `except Exception -> retryable=True` retried a ValueError three
#: times and, worse, retried a RunAborted that should have stopped the run.
TRANSIENT_EXCEPTIONS = (TimeoutError, ConnectionError)


class TransportError(Exception):
    """A single attempt failed in a way the caller may consider retrying."""

    def __init__(self, message, status=None, retryable=False):
        super().__init__(message)
        self.status = status
        self.retryable = retryable


class RunAborted(Exception):
    """The whole run must stop now: ceiling reached, or the vendor said stop."""


@dataclass
class Response:
    status: int
    text: str
    url: str
    headers: dict = field(default_factory=dict)


@dataclass
class Attempt:
    url: str
    source: str
    status: object
    outcome: str
    waited: float


class PacedTransport:
    """Counts, paces and bounds every HTTP attempt.

    `transport(url, timeout, allow_redirects)` is injected. Tests pass a fake; the live
    adapter is never wired in during M2a.
    """

    def __init__(self, transport, *, clock, sleeper,
                 min_interval=DEFAULT_MIN_INTERVAL, ceiling=DEFAULT_CEILING,
                 connect_timeout=CONNECT_TIMEOUT, read_timeout=READ_TIMEOUT,
                 session=None):
        def finite_positive(name, value):
            # `float("inf") > 0` is True, which is how an infinite connect timeout
            # previously passed a check that claimed to enforce finiteness.
            try:
                number = float(value)
            except (TypeError, ValueError):
                raise ValueError("%s must be a number, got %r" % (name, value)) from None
            if not math.isfinite(number) or number <= 0:
                raise ValueError("%s must be finite and positive, got %r" % (name, value))
            return number

        min_interval = finite_positive("min_interval", min_interval)
        connect_timeout = finite_positive("connect_timeout", connect_timeout)
        read_timeout = finite_positive("read_timeout", read_timeout)
        if not isinstance(ceiling, int) or ceiling <= 0:
            raise ValueError("ceiling must be a positive integer, got %r" % (ceiling,))
        if session is not None:
            # Enforced at construction, not merely available as a helper.
            assert_no_hidden_retries(session)
        self._transport = transport
        self._clock = clock
        self._sleeper = sleeper
        self.min_interval = float(min_interval)
        self.ceiling = int(ceiling)
        self.timeout = (float(connect_timeout), float(read_timeout))
        self.attempts: list[Attempt] = []
        self._last_call_at = {}
        self.aborted_reason = None

    # ------------------------------------------------------------------ accounting
    @property
    def attempt_count(self) -> int:
        return len(self.attempts)

    def remaining(self) -> int:
        return max(0, self.ceiling - self.attempt_count)

    def _pace(self, source) -> float:
        """Wait out the per-source interval. Returns how long we waited."""
        last = self._last_call_at.get(source)
        now = self._clock()
        waited = 0.0
        if last is not None:
            gap = now - last
            if gap < self.min_interval:
                waited = self.min_interval - gap
                self._sleeper(waited)
        self._last_call_at[source] = self._clock()
        return waited

    # ---------------------------------------------------------------------- request
    def get(self, url, *, source):
        """One HTTP attempt: paced, counted, bounded, finite."""
        if self.aborted_reason:
            raise RunAborted(self.aborted_reason)
        if self.attempt_count >= self.ceiling:
            self.aborted_reason = ("attempt ceiling %d reached" % self.ceiling)
            raise RunAborted(self.aborted_reason)

        waited = self._pace(source)

        def record(status, outcome):
            self.attempts.append(Attempt(url=url, source=source, status=status,
                                         outcome=outcome, waited=waited))

        try:
            response = self._transport(url, timeout=self.timeout, allow_redirects=False)
        except RunAborted as exc:
            # A whole-run stop must never be downgraded into a retryable attempt error,
            # AND it must be sticky. Propagating without latching the reason left
            # `aborted_reason` NULL, so the very next call sailed through with 200 and
            # the attempt count kept climbing.
            record("RunAborted", "stop")
            if not self.aborted_reason:
                self.aborted_reason = str(exc) or "transport raised RunAborted"
            raise
        except TRANSIENT_EXCEPTIONS as exc:
            record(type(exc).__name__, "transient")
            raise TransportError("transient transport error: %s" % exc,
                                 retryable=True) from exc
        except Exception as exc:                      # noqa: BLE001
            record(type(exc).__name__, "error")
            raise TransportError("non-transient transport error: %s" % exc,
                                 retryable=False) from exc

        status = int(getattr(response, "status", 0))

        if status in STOP_STATUS:
            record(status, "stop")
            self.aborted_reason = (
                "vendor returned %d; stopping the entire run immediately and NOT "
                "retrying - backing off into a soft rate limit is how it becomes a ban"
                % status)
            raise RunAborted(self.aborted_reason)

        if 300 <= status < 400:
            # Following this would be an uncounted, unpaced second attempt.
            record(status, "redirect")
            raise TransportError(
                "redirect %d to %r refused: following it would be an HTTP attempt "
                "outside the ceiling and the pacing" % (status, response.headers.get("location")),
                status=status, retryable=False)

        if status in RETRYABLE_STATUS:
            record(status, "retryable")
            raise TransportError("server error %d" % status, status=status, retryable=True)

        if status != 200:
            record(status, "failed")
            raise TransportError("unexpected status %d" % status, status=status,
                                 retryable=False)

        record(status, "ok")
        return response

    # ---------------------------------------------------------------------- retries
    def get_with_retries(self, url, *, source, max_attempts=MAX_ATTEMPTS_PER_JOB):
        """Bounded, explicit, counted retries at the REQUEST level.

        `max_attempts` counts attempts for THIS request, not for the symbol job: a stock
        job issues two requests and may therefore consume up to 2 x max_attempts of the
        global ceiling. A RunAborted is never retried.
        """
        if not isinstance(max_attempts, int) or not 1 <= max_attempts <= MAX_ATTEMPTS_PER_JOB:
            raise ValueError("max_attempts must be 1..%d, got %r"
                             % (MAX_ATTEMPTS_PER_JOB, max_attempts))
        last = None
        for index in range(max_attempts):
            try:
                return self.get(url, source=source)
            except RunAborted:
                raise
            except TransportError as exc:
                last = exc
                if not exc.retryable or index == max_attempts - 1:
                    raise
                self._sleeper(BACKOFF[min(index, len(BACKOFF) - 1)])
        raise last                                    # pragma: no cover - unreachable


def assert_no_hidden_retries(session) -> None:
    """Fail closed if a live session would retry underneath our counter.

    urllib3 retries do not pass through PacedTransport, so they would be invisible to
    both the ceiling and the pacing.
    """
    for adapter in getattr(session, "adapters", {}).values():
        retries = getattr(adapter, "max_retries", None)
        total = getattr(retries, "total", retries)
        if total not in (0, False, None):
            raise RunAborted(
                "adapter has library-level retries enabled (total=%r); disable them so "
                "every attempt is counted and paced" % (total,))
        if getattr(retries, "redirect", 0) not in (0, False, None):
            raise RunAborted("adapter would follow redirects internally; disable it")


class LiveTransport:
    """Placeholder for the eventual live adapter. Refuses to run in M2a."""

    def __init__(self, *, armed=False):
        self.armed = armed

    def __call__(self, url, *, timeout, allow_redirects):
        if not self.armed:
            raise RunAborted(
                "live transport is not armed: M2a is offline-only and performs no "
                "network request")
        raise RunAborted("live transport is not implemented in M2a")   # pragma: no cover
