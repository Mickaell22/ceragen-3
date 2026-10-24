from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuracion leida de variables de entorno. Sin defaults para secretos:
    si falta una variable obligatoria, la API no arranca."""

    # Sin esto, un error de validacion imprime los valores (y la password) en el log.
    model_config = SettingsConfigDict(hide_input_in_errors=True)

    database_url: SecretStr
    cors_origins: str

    # HS256 con menos de 32 bytes de secreto es atacable por fuerza bruta offline.
    jwt_secret: SecretStr = Field(min_length=32)
    jwt_expire_minutes: int = Field(gt=0)
    login_max_attempts: int = Field(gt=0)
    login_lock_minutes: int = Field(gt=0)

    # Cookie de sesión. Front y API en el mismo sitio (localhost, o dominio propio
    # con subdominios): lax. En sitios distintos (dos *.up.railway.app, que es un
    # sufijo público): none, que obliga a secure.
    cookie_secure: bool
    cookie_samesite: Literal["lax", "strict", "none"]

    @model_validator(mode="after")
    def _samesite_none_needs_secure(self) -> "Settings":
        if self.cookie_samesite == "none" and not self.cookie_secure:
            raise ValueError("COOKIE_SAMESITE=none exige COOKIE_SECURE=true (los navegadores la rechazan)")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
