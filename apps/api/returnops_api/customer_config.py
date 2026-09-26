"""Explicit private demo verification configuration. No login or default key."""
import base64,json,os
from pathlib import Path
from .security.authentication import AuthConfig
from .settings import ConfigurationError

def load_private_auth_config():
    path=os.environ.get('RETURNOPS_AUTH_FILE')
    if not path: return None
    failed=False
    try:
        source=Path(path)
        if not source.is_absolute() or source.stat().st_size>8192: raise ValueError()
        value=json.loads(source.read_text(encoding='utf-8'))
        if set(value)!={'issuer','audience','signing_key_base64'}: raise ValueError()
        key=base64.b64decode(value['signing_key_base64'],validate=True)
        return AuthConfig(value['issuer'],value['audience'],key,leeway_seconds=0)
    except (OSError,ValueError,TypeError): failed=True
    if failed: raise ConfigurationError('Configure an explicit valid private demo authentication file.') from None
