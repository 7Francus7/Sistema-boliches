from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://boliche:boliche@localhost:5432/boliche"
    jwt_secret: str = "dev-change-me"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 60 * 12
    env: str = "dev"

    def model_post_init(self, __context) -> None:
        # Render/Railway exponen DATABASE_URL como postgres:// o postgresql://
        # sin el driver. SQLAlchemy + psycopg3 requiere postgresql+psycopg://.
        url = self.database_url
        if url.startswith("postgres://"):
            url = "postgresql+psycopg://" + url[len("postgres://") :]
        elif url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://") :]
        self.database_url = url


settings = Settings()
