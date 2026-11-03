"""Fail-closed OIDC/JWT bearer authentication for protected API routes."""
from __future__ import annotations
from typing import Any
import jwt
from jwt import PyJWKClient
from app.config import Settings
class AuthenticationError(RuntimeError):
    def __init__(self, message: str = "A valid bearer token is required.", status_code: int = 401):
        super().__init__(message)
        self.status_code = status_code
class OIDCAuthenticator:
    """Verify RS256 access tokens against the configured OIDC issuer and JWKS."""
    def __init__(self, config: Settings):
        self.config = config
        self._jwks_client: PyJWKClient | None = None
    def authenticate(self, authorization: str | None) -> dict[str, Any]:
        if not self.config.oidc_configured:
            if self.config.is_production:
                raise AuthenticationError("API identity verification is not configured.", 503)
            return {"sub": "development-user", "auth_mode": "development"}
        if self.config.is_production:
            secure_urls = (self.config.oidc_issuer or "").startswith("https://") and (self.config.oidc_jwks_url or "").startswith("https://")
            if not secure_urls or not self.config.oidc_required_scope:
                raise AuthenticationError("Production identity issuer, JWKS and required scope must be configured.", 503)
        if not authorization or not authorization.startswith("Bearer "):
            raise AuthenticationError()
        token = authorization[7:].strip()
        if not token or len(token) > 16384:
            raise AuthenticationError()
        try:
            if self._jwks_client is None:
                self._jwks_client = PyJWKClient(self.config.oidc_jwks_url, cache_jwk_set=True, lifespan=300)
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)
            claims = jwt.decode(token, signing_key.key, algorithms=["RS256"], audience=self.config.oidc_audience,
                                issuer=self.config.oidc_issuer, options={"require": ["exp", "iat", "sub"]})
        except Exception as exc:
            raise AuthenticationError() from exc
        if not isinstance(claims.get("sub"), str) or not claims["sub"].strip():
            raise AuthenticationError()
        required_scope = self.config.oidc_required_scope
        if required_scope:
            scopes = claims.get("scope", "")
            scope_set = set(scopes.split()) if isinstance(scopes, str) else set()
            scp = claims.get("scp", [])
            if isinstance(scp, list): scope_set.update(str(value) for value in scp)
            if required_scope not in scope_set:
                raise AuthenticationError("The token does not grant the required API scope.", 403)
        return claims
