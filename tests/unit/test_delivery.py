from fastapi.testclient import TestClient

from planner.app import create_app
from planner.settings import Settings


def test_same_origin_image_serves_assets_without_swallowing_api(tmp_path):
    (tmp_path / "index.html").write_text("<html><body>synthetic planner</body></html>")
    (tmp_path / "asset.js").write_text('console.log("synthetic")')
    with TestClient(create_app(Settings(static_dist_path=tmp_path))) as api:
        assert "synthetic planner" in api.get("/").text
        assert api.get("/asset.js").status_code == 200
        assert api.get("/api/v1/not-a-route").status_code == 404
        assert api.get("/health/live").json() == {"status": "ok"}


def test_database_parts_quote_secrets_and_hide_password_repr():
    settings = Settings(
        database_host="synthetic.invalid",
        database_username="planner_app",
        database_password="private:@/password",
        database_name="planner",
        database_sslmode="require",
    )
    from sqlalchemy.engine import make_url

    url = make_url(settings.database_url)
    assert url.password == "private:@/password"
    assert url.host == "synthetic.invalid" and url.query["sslmode"] == "require"
    assert "private:" not in repr(settings)
