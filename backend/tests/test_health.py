from app import routes


class _FakeConn:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, _stmt):
        return None


class _FakeEngine:
    def connect(self):
        return _FakeConn()


class _DownEngine:
    def connect(self):
        raise OSError("connection refused")


def test_health_is_public_and_ok(client, monkeypatch):
    monkeypatch.setattr(routes, "get_engine", lambda _url: _FakeEngine())
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json == {"status": "ok"}


def test_health_reports_db_down(client, monkeypatch):
    monkeypatch.setattr(routes, "get_engine", lambda _url: _DownEngine())
    res = client.get("/api/health")
    assert res.status_code == 503
    assert res.json["error"]["code"] == "db_unavailable"
