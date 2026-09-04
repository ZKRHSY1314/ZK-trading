from scripts import control_plane_loop


def test_control_plane_retries_unsuccessful_cycles_before_regular_interval() -> None:
    assert control_plane_loop.next_interval_seconds("failed", 900) == 300
    assert control_plane_loop.next_interval_seconds("blocked", 900) == 300
    assert control_plane_loop.next_interval_seconds("partial", 900) == 300
    assert control_plane_loop.next_interval_seconds("completed", 900) == 900
    assert control_plane_loop.next_interval_seconds("failed", 120) == 120


def test_control_plane_request_uses_the_declared_cycle_timeout(monkeypatch) -> None:
    observed_timeouts: list[int] = []

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        @staticmethod
        def read() -> bytes:
            return b'{"status":"completed"}'

    def _urlopen(_request, *, timeout):
        observed_timeouts.append(timeout)
        return _Response()

    monkeypatch.setattr(control_plane_loop.urllib.request, "urlopen", _urlopen)

    result = control_plane_loop.request_json(
        "GET",
        "http://127.0.0.1:8000/health",
        timeout=17,
    )

    assert result["status"] == "completed"
    assert observed_timeouts == [17]
