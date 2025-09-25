from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Redis/CORS (existing)
    REDIS_URL: str = "redis://localhost:6379/0"
    CORS_ALLOW_ORIGINS: str = "*"

    # --- OAuth / Entra ID ---
    AUTH_REQUIRED: bool = False  # set True in docker-compose to enforce
    ENTRA_TENANT_ID: str | None = None  # e.g., "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    # Comma-separated audiences allowed. Examples:
    #  - "api://<app-id-uri>"
    #  - "<server-app-client-id>"
    ENTRA_AUDIENCES: str | None = None
    # Optional scopes list, comma-separated. Example: "Mcp.Invoke"
    ENTRA_REQUIRED_SCOPES: str | None = None
    # Optional app roles list, comma-separated. Example: "Mcp.Invoke"
    ENTRA_REQUIRED_APP_ROLES: str | None = None

    @property
    def issuer(self) -> str | None:
        # v2.0 endpoint issuer format for tokens
        return f"https://login.microsoftonline.com/{self.ENTRA_TENANT_ID}/v2.0" if self.ENTRA_TENANT_ID else None

    @property
    def jwks_url(self) -> str | None:
        # JWKS endpoint to fetch signing keys
        return f"https://login.microsoftonline.com/{self.ENTRA_TENANT_ID}/discovery/v2.0/keys" if self.ENTRA_TENANT_ID else None

settings = Settings()
