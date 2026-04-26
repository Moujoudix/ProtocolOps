from app.core.config import Settings


def test_cors_allow_origins_parses_comma_separated_values():
    settings = Settings(
        backend_cors_allow_origins="https://app.example.com, https://staging.example.com ,http://localhost:5173",
    )

    assert settings.cors_allow_origins == [
        "https://app.example.com",
        "https://staging.example.com",
        "http://localhost:5173",
    ]


def test_cors_allow_origin_regex_is_available_when_set():
    settings = Settings(
        backend_cors_allow_origin_regex=r"https://.*\.preview\.example\.com",
    )

    assert settings.backend_cors_allow_origin_regex == r"https://.*\.preview\.example\.com"
