"""Explicit trusted composition; no route, default adapter or automatic grant."""
from returnops_domain.pass_review import PassReviewReceiver


def compose_private_pass_review(engine, controlled_adapter, **options):
    """REVIEW service authority is checked inside each fenced transaction."""
    return PassReviewReceiver(engine, controlled_adapter, **options)
