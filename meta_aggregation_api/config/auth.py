from fastapi_jwt_auth import AuthJWT
from pydantic import BaseSettings


class AuthConfig(BaseSettings):
    authjwt_secret_key: str = 'secretkey'


@AuthJWT.load_config
def get_config():
    return AuthConfig()
