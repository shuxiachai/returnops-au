"""Explicit private return-source bridge composition; no route or startup work."""
from returnops_domain.return_label_bridge import ReturnLabelBridge
from .customer_authority import CurrentRequestAuthority


def compose_private_return_label_bridge(engine, auth_config, authorization, **options):
    return ReturnLabelBridge(engine, CurrentRequestAuthority(auth_config, authorization), **options)
