"""Unregistered private Operations composition; no route or startup consumer."""
from returnops_domain.return_execution import ReturnExecutionService
from .customer_authority import CurrentRequestAuthority


def compose_private_return_execution(engine, auth_config, authorization, **options):
    return ReturnExecutionService(engine, CurrentRequestAuthority(auth_config, authorization), **options)
