"""Explicit server composition; no route, startup producer or grant creation."""
from returnops_domain.review_escalation import EscalateReviewReceiver


def compose_private_review(engine,controlled_adapter,**options):
    """The adapter is trusted server code, never selected from a request DTO."""
    return EscalateReviewReceiver(engine,controlled_adapter,**options)
