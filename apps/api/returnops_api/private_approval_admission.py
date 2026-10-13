"""Unregistered private read-only composition; no HTTP route or producer."""
from returnops_domain.approval_admission import ApprovalAdmissionService
from .customer_authority import CurrentRequestAuthority


def compose_private_approval_admission(engine, auth_config, authorization, **options):
    return ApprovalAdmissionService(engine, CurrentRequestAuthority(auth_config, authorization), **options)
