"""Explicit private composition; no routes, background startup or auto grants."""
from returnops_domain.notification_service import NotificationService
from .customer_authority import CurrentRequestAuthority


def compose_private_notification(engine, auth_config, authorization, **options):
    return NotificationService(engine,CurrentRequestAuthority(auth_config,authorization),**options)
