"""Unregistered private label composition. No HTTP route or startup consumer."""
from returnops_domain.label_execution import LabelExecutionService
from .customer_authority import CurrentRequestAuthority


def compose_private_label_execution(engine,auth_config,authorization,**options):
    return LabelExecutionService(engine,CurrentRequestAuthority(auth_config,authorization),**options)
