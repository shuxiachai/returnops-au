"""Unregistered private durable preparation; no HTTP route or startup producer."""
from returnops_domain.execution_preparation import ExecutionPreparationService
from .customer_authority import CurrentRequestAuthority


def compose_private_execution_preparation(engine, auth_config, authorization, **options):
    return ExecutionPreparationService(engine, CurrentRequestAuthority(auth_config, authorization), **options)
