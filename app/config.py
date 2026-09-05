from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Environment bootstrap. Only what must exist before the app can start lives here.
    Organisation settings (report recipients, mail, schedule) are edited in the app and stored
    in DATA_DIR/settings.json; the matching env vars below are just their first-run defaults."""

    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",   # .env also carries values for Caddy (TRACKWORK_DOMAIN); never crash on them
    )

    # App
    secret_key: str = ""
    environment: str = "production"      # "development" disables the secure cookie flag (local http)
    public_read: bool = False            # true lets anyone read without signing in
    data_dir: str = "./data"             # everything the app writes; mount this as the Docker volume

    # Email bootstrap defaults (overridden by data/settings.json once saved from the admin screen)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    report_email_recipient: str = ""     # comma separated
    report_email_sender: str = ""

    # Weekly report runs inside the web process (no external cron to configure)
    scheduler_enabled: bool = True

    # MCP (AI assistant) server, mounted inside the web app at /mcp
    mcp_enabled: bool = False
    mcp_auth_provider: str = "token"     # azure | google | github | token | none
    mcp_base_url: str = ""               # public https URL of this app; required by the OAuth providers
    mcp_oauth_client_id: str = ""
    mcp_oauth_client_secret: str = ""
    mcp_oauth_tenant: str = ""           # azure only

    @property
    def secure_cookies(self) -> bool:
        return self.environment == "production"

    def _data_root(self) -> Path:
        p = Path(self.data_dir)
        return p if p.is_absolute() else _PROJECT_ROOT / p

    @property
    def projects_dir(self) -> Path:
        return self._data_root() / "projects"

    @property
    def archived_dir(self) -> Path:
        return self._data_root() / "archived"

    @property
    def users_file(self) -> Path:
        return self._data_root() / "users.json"

    @property
    def config_file(self) -> Path:
        """Equipment list."""
        return self._data_root() / "config.json"

    @property
    def settings_file(self) -> Path:
        """Organisation settings (recipients, mail, schedule, names)."""
        return self._data_root() / "settings.json"

    @property
    def scheduler_state_file(self) -> Path:
        return self._data_root() / "scheduler_state.json"

    @property
    def mcp_tokens_file(self) -> Path:
        return self._data_root() / "mcp_tokens.json"


settings = Settings()
