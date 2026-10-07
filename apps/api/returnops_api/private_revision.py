"""Explicit trusted Founder revision composition; no route or grant provisioning."""
from returnops_domain.revision_decision import FounderRevisionService
from .customer_authority import CurrentRequestAuthority


def compose_private_revision(engine, auth_config, authorization, **options):
    return FounderRevisionService(engine, CurrentRequestAuthority(auth_config, authorization), **options)
