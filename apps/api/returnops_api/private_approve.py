"""Private trusted Founder composition only; no public POST or execution."""
from returnops_domain.approve_decision import FounderApproveService
from .customer_authority import CurrentRequestAuthority


def compose_private_approve(engine, auth_config, authorization, **options):
    return FounderApproveService(engine, CurrentRequestAuthority(auth_config, authorization), **options)
