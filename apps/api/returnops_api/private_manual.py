"""Explicit trusted composition only; no public route or default producer.

The caller supplies server AuthConfig and the actual request authorization;
request bodies cannot supply a principal or SERVICE capability.
"""
from returnops_domain.manual_decision import FounderDecisionService
from .customer_authority import CurrentRequestAuthority


def compose_private_manual(engine, auth_config, authorization, **options):
    return FounderDecisionService(engine, CurrentRequestAuthority(auth_config, authorization), **options)
