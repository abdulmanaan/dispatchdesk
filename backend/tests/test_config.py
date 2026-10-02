"""Tests for settings helpers."""

import pytest

from app.core.config import normalize_database_url


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "postgresql://u:p@ep-x.neon.tech/db?sslmode=require&channel_binding=require",
            "postgresql+asyncpg://u:p@ep-x.neon.tech/db?ssl=require",
        ),
        (
            "postgres://u:p@localhost:5432/db",
            "postgresql+asyncpg://u:p@localhost:5432/db",
        ),
        (
            "postgresql+asyncpg://u:p@localhost:5432/db",
            "postgresql+asyncpg://u:p@localhost:5432/db",
        ),
        (
            "postgresql://u:p@localhost/db?sslmode=disable",
            "postgresql+asyncpg://u:p@localhost/db",
        ),
    ],
)
def test_normalize_database_url(raw: str, expected: str) -> None:
    assert normalize_database_url(raw) == expected


def test_cors_origins_from_comma_separated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import Settings

    monkeypatch.setenv("CORS_ORIGINS", "https://dispatchdesk.vercel.app/, http://localhost:5173")

    assert Settings(_env_file=None).cors_origins == [
        "https://dispatchdesk.vercel.app",
        "http://localhost:5173",
    ]


async def test_cors_preflight_allows_frontend(client) -> None:
    response = await client.options(
        "/auth/login",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
