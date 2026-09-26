"""F.03 JWT verification and current registration checks, without HTTP or DB.

FR-009/012, NFR-002/003/009; docs/16 AUTH-01/02/07/12; CS-D01,
MA G-REQUEST. PyJWT performs signature/issuer/audience/time validation.
This component never issues tokens and ignores token-supplied authority claims.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import re

import jwt

from .errors import SecurityDependencyError, SecurityStoreUnavailable, Unauthenticated
from .types import (
    IdentitySnapshot, IdentityStore, PrincipalRecord, Role, SessionRecord,
    VerifiedPrincipal, valid_id,
)


@dataclass(frozen=True, slots=True)
class AuthConfig:
    issuer: str
    audience: str
    signing_key: bytes = field(repr=False)
    max_ttl_seconds: int = 900
    leeway_seconds: int = 5

    def __post_init__(self) -> None:
        # Private, locally generated high-entropy bytes are required at integration.
        # Length validation alone cannot prove entropy; no secrets are generated here.
        if not isinstance(self.signing_key, bytes) or not 32 <= len(self.signing_key) <= 128:
            raise ValueError("Configure a private HS256 key of 32 to 128 bytes.")
        for value in (self.issuer, self.audience):
            if not isinstance(value, str) or not 1 <= len(value) <= 200 or not value.isascii() or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in value):
                raise ValueError("Configure non-empty bounded ASCII issuer and audience values.")
        if type(self.max_ttl_seconds) is not int or not 1 <= self.max_ttl_seconds <= 900:
            raise ValueError("Session lifetime must be between 1 and 900 seconds.")
        if type(self.leeway_seconds) is not int or not 0 <= self.leeway_seconds <= 5:
            raise ValueError("Clock leeway must be between 0 and 5 seconds.")


class Authenticator:
    def __init__(self, config: AuthConfig, identities: IdentityStore) -> None:
        self._config = config
        self._identities = identities

    def authenticate(self, authorization: str | None) -> VerifiedPrincipal:
        """Accept only an explicit Bearer header, never cookie/query/body identity.

        Every call verifies the token and rereads both current registry records.
        A grant must be rechecked inside a future Domain write/dispatch transaction;
        this independent read does not implement that transaction or eliminate races.
        """
        if not isinstance(authorization, str) or len(authorization) > 4096:
            raise Unauthenticated()
        match = re.fullmatch(r"(?i:Bearer) +([A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)", authorization)
        if match is None:
            raise Unauthenticated()
        token = match.group(1)
        try:
            decoded = jwt.decode_complete(
                token,
                self._config.signing_key,
                algorithms=["HS256"],
                issuer=self._config.issuer,
                audience=self._config.audience,
                leeway=self._config.leeway_seconds,
                options={
                    "require": ["iss", "aud", "sub", "jti", "iat", "nbf", "exp"],
                    "strict_aud": True,
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_iat": True,
                    "verify_nbf": True,
                    "verify_iss": True,
                    "verify_aud": True,
                    "verify_sub": True,
                    "verify_jti": True,
                },
            )
        except (jwt.InvalidTokenError, TypeError, ValueError, OverflowError):
            raise Unauthenticated() from None
        header, claims = decoded["header"], decoded["payload"]
        # No attacker-selected keys, remote JWKS URLs or unsupported critical headers.
        if set(header) != {"alg", "typ"} or header.get("typ") != "JWT":
            raise Unauthenticated()
        if not valid_id(claims["sub"]) or not valid_id(claims["jti"]):
            raise Unauthenticated()
        times = [claims[name] for name in ("iat", "nbf", "exp")]
        if any(type(value) is not int or value < 0 or value > 9007199254740991 for value in times):
            raise Unauthenticated()
        issued, not_before, expires = times
        if not issued <= not_before < expires or expires - issued > self._config.max_ttl_seconds:
            raise Unauthenticated()
        try:
            current = self._identities.read_identity(claims["sub"], claims["jti"])
        except SecurityStoreUnavailable:
            raise SecurityDependencyError() from None
        if current is None:
            raise Unauthenticated()
        if not isinstance(current, IdentitySnapshot):
            raise SecurityDependencyError()
        principal, session = current.principal, current.session
        if not isinstance(principal, PrincipalRecord) or not isinstance(session, SessionRecord):
            raise SecurityDependencyError()
        if (
            principal.principal_id != claims["sub"]
            or not isinstance(principal.role, Role)
            or not valid_id(principal.store_id)
            or principal.enabled is not True
            or session.session_id != claims["jti"]
            or session.principal_id != principal.principal_id
            or session.revoked is not False
            or any(type(value) is not int for value in (session.issued_at, session.not_before, session.expires_at))
            or (session.issued_at, session.not_before, session.expires_at) != tuple(times)
        ):
            raise Unauthenticated()
        # A slow registry lookup must not return a session that expired meanwhile.
        now = datetime.now(timezone.utc).timestamp()
        leeway = self._config.leeway_seconds
        if issued > now + leeway or not_before > now + leeway or expires <= now - leeway:
            raise Unauthenticated()
        # Current server role/store win even if a correctly signed token says otherwise.
        return VerifiedPrincipal(principal.principal_id, principal.role, principal.store_id, session.session_id)
