from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuracion leida de variables de entorno. Sin defaults para secretos:
    si falta una variable obligatoria, la API no arranca."""

    # Sin esto, un error de validacion imprime los valores (y la password) en el log.
    model_config = SettingsConfigDict(hide_input_in_errors=True)

    database_url: SecretStr
    cors_origins: str

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
