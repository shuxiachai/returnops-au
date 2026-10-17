"""Explicit private server composition; no public route, grant or producer."""
from returnops_domain.preview_service import PreviewService


def compose_private_preview(engine, **options):
    return PreviewService(engine, **options)
