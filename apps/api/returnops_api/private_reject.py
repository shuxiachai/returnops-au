"""Explicit trusted composition only; no public route or default producer."""
from returnops_domain.reject_decision import FounderRejectService
from .customer_authority import CurrentRequestAuthority


def compose_private_reject(engine, auth_config, authorization, **options):
    return FounderRejectService(engine, CurrentRequestAuthority(auth_config, authorization), **options)
