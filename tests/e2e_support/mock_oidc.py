"""Ephemeral local OIDC/JWKS fixture for CI only. Never use for production identity."""
from __future__ import annotations

import base64
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

HOST = "127.0.0.1"
PORT = 8081
ISSUER = f"http://{HOST}:{PORT}/"
AUDIENCE = "eor-atlas-e2e"
REQUIRED_SCOPE = "eor.atlas.access"
KEY_ID = "ephemeral-e2e-key"

# A fresh key pair is generated for each workflow run and never written to disk.
_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PUBLIC_NUMBERS = _PRIVATE_KEY.public_key().public_numbers()


def _b64url_uint(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, byteorder="big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


_JWKS = {
    "keys": [{
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": KEY_ID,
        "n": _b64url_uint(_PUBLIC_NUMBERS.n),
        "e": _b64url_uint(_PUBLIC_NUMBERS.e),
    }]
}


def _issue_token(scope: str) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "iss": ISSUER,
            "aud": AUDIENCE,
            "sub": "eor-atlas-ci-user",
            "iat": now,
            "exp": now + 300,
            "scope": scope,
        },
        _PRIVATE_KEY,
        algorithm="RS256",
        headers={"kid": KEY_ID, "typ": "JWT"},
    )


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, value: object) -> None:
        body = json.dumps(value).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/jwks":
            self._send_json(_JWKS)
        elif parsed.path == "/token":
            query = parse_qs(parsed.query)
            scope = query.get("scope", [REQUIRED_SCOPE])[0]
            self._send_json({"access_token": _issue_token(scope), "token_type": "Bearer"})
        elif parsed.path == "/health":
            self._send_json({"status": "ok"})
        else:
            self.send_error(404)

    def log_message(self, _format: str, *_args: object) -> None:
        # Keep temporary test tokens and request headers out of workflow logs.
        return


if __name__ == "__main__":
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()