from __future__ import annotations
import pytest
from app.auth import AuthenticationError, OIDCAuthenticator
from app.config import Settings

def test_development_without_oidc_is_explicitly_local_only():
    config=Settings(environment="development",oidc_issuer=None,oidc_audience=None,oidc_jwks_url=None)
    assert OIDCAuthenticator(config).authenticate(None)["auth_mode"]=="development"

def test_production_without_oidc_fails_closed():
    config=Settings(environment="production",oidc_issuer=None,oidc_audience=None,oidc_jwks_url=None)
    with pytest.raises(AuthenticationError) as error: OIDCAuthenticator(config).authenticate(None)
    assert error.value.status_code==503

def test_production_requires_https_and_required_scope_before_token_processing():
    config=Settings(environment="production",oidc_issuer="https://issuer.example",oidc_audience="eor-api",
        oidc_jwks_url="https://issuer.example/jwks",oidc_required_scope=None)
    with pytest.raises(AuthenticationError,match="required scope") as error: OIDCAuthenticator(config).authenticate("Bearer any-token")
    assert error.value.status_code==503
