"""A1.06 showcase model configuration, from the environment only (docs/44).

F.07 / NFR-003/007/008: the key is a SecretStr and is never echoed by errors,
repr or str; demo.py accepts no key argument. Errors name the variable only.
"""
import os

from pydantic import BaseModel, ConfigDict, SecretStr

from returnops_domain.coordinator_showcase import ShowcaseSettings
from returnops_domain.errors import FlowError
from returnops_domain.model_transport import (DIALECT, MAX_DEADLINE_SECONDS, BudgetedTransport,
    ChatCompletionsTransport, validate_base_url, validate_proxy_url)
from returnops_domain.wire import validate

from .settings import ConfigurationError

REQUIRED = ('RETURNOPS_MODEL_BASE_URL', 'RETURNOPS_MODEL_API_KEY', 'RETURNOPS_MODEL_ID', 'RETURNOPS_MODEL_PROVIDER_ID')


def _fail(message):
    raise ConfigurationError(message) from None


class ModelSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())
    base_url: str
    api_key: SecretStr
    model_id: str
    provider_id: str
    deadline_seconds: int = 20
    dialect: str = DIALECT
    proxy_url: str | None = None
    allow_private_http: bool = False
    # Optional cap on model calls in this process; Railway sets it (31 October 2026).
    max_calls: int | None = None

    @classmethod
    def from_environment(cls, environ=None) -> "ModelSettings":
        env = os.environ if environ is None else environ
        missing = [name for name in REQUIRED if not env.get(name)]
        if missing:
            _fail("Set " + ", ".join(missing) + " for the model showcase (RETURNOPS_MODEL_SHOWCASE=1).")
        failed = False
        private_http = env.get("RETURNOPS_MODEL_ALLOW_PRIVATE_HTTP") or "0"
        if private_http not in ("0", "1"):
            _fail("Set RETURNOPS_MODEL_ALLOW_PRIVATE_HTTP to 0 or 1.")
        try:
            base_url = validate_base_url(env["RETURNOPS_MODEL_BASE_URL"], allow_private_http=private_http == "1")
        except ValueError:
            failed = True
        if failed:
            _fail("Set RETURNOPS_MODEL_BASE_URL to an https URL without credentials, query or fragment"
                  " (plain http only to a private IPv4 address with a port, and only with RETURNOPS_MODEL_ALLOW_PRIVATE_HTTP=1).")
        key = env["RETURNOPS_MODEL_API_KEY"]
        if not (1 <= len(key) <= 512 and key.isascii() and key.isprintable() and not any(c.isspace() for c in key)):
            _fail("Set RETURNOPS_MODEL_API_KEY to a non-empty key without whitespace.")
        model_id = env["RETURNOPS_MODEL_ID"]
        if not (1 <= len(model_id) <= 120 and model_id.isascii() and model_id.isprintable()):
            _fail("Set RETURNOPS_MODEL_ID to 1-120 printable ASCII characters.")
        provider_id = env["RETURNOPS_MODEL_PROVIDER_ID"]
        try:
            validate("Id", provider_id)
        except FlowError:
            failed = True
        if failed:
            _fail("Set RETURNOPS_MODEL_PROVIDER_ID to a contract Id (letters, digits, _ or -, 3-80 characters).")
        deadline = env.get("RETURNOPS_MODEL_DEADLINE_SECONDS") or "20"
        if not (deadline.isascii() and deadline.isdigit() and 1 <= int(deadline) <= MAX_DEADLINE_SECONDS):
            # Below the 60 s claim lease, which is also renewed after the call.
            _fail("Set RETURNOPS_MODEL_DEADLINE_SECONDS to a whole number from 1 to 50.")
        dialect = env.get("RETURNOPS_MODEL_DIALECT") or DIALECT
        if dialect != DIALECT:
            _fail("RETURNOPS_MODEL_DIALECT supports only chat-completions.")
        proxy = env.get("RETURNOPS_MODEL_PROXY_URL") or None
        if proxy is not None:
            try:
                validate_proxy_url(proxy)
            except ValueError:
                failed = True
            if failed:
                _fail("Set RETURNOPS_MODEL_PROXY_URL to http(s)://host:port without credentials.")
        max_calls = env.get("RETURNOPS_MODEL_MAX_CALLS") or None
        if max_calls is not None and not (max_calls.isascii() and max_calls.isdigit() and 1 <= int(max_calls) <= 100000):
            _fail("Set RETURNOPS_MODEL_MAX_CALLS to a whole number from 1 to 100000, or leave it unset.")
        return cls(base_url=base_url, api_key=SecretStr(key), model_id=model_id, provider_id=provider_id,
                   deadline_seconds=int(deadline), dialect=dialect, proxy_url=proxy,
                   allow_private_http=private_http == "1", max_calls=None if max_calls is None else int(max_calls))

    def transport(self):
        transport = ChatCompletionsTransport(self.base_url, self.api_key, self.model_id,
                                             deadline_seconds=self.deadline_seconds, proxy_url=self.proxy_url,
                                             allow_private_http=self.allow_private_http)
        return transport if self.max_calls is None else BudgetedTransport(transport, self.max_calls)

    def worker_settings(self) -> ShowcaseSettings:
        return ShowcaseSettings(provider_id=self.provider_id, model_id=self.model_id)
