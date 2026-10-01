"""Private A1.03 event references; no wire DTO or arbitrary status setter.

Future deterministic producers save their source and binding on the same fenced
connection, then submit one of these references. This module does not produce
proposals, reviews, decisions, approvals, operations, or notifications.
"""
from dataclasses import dataclass


@dataclass(frozen=True, slots=True, repr=False)
class LifecycleClaim:
    work_id: str
    claim_id: str
    epoch: int
    case_version: int
    input_version: int
    generation: int
    authority_revision: int


@dataclass(frozen=True, slots=True, repr=False)
class SourceEvent:
    event_id: str
    claim: LifecycleClaim
    record_id: str


@dataclass(frozen=True, slots=True, repr=False)
class ProposalAccepted(SourceEvent):
    pass


@dataclass(frozen=True, slots=True, repr=False)
class RevisionRequested(SourceEvent):
    pass


@dataclass(frozen=True, slots=True, repr=False)
class OutcomeAccepted(SourceEvent):
    notification_record_id: str
    return_record_id: str | None = None
    label_record_id: str | None = None


@dataclass(frozen=True, slots=True, repr=False)
class NotificationObserved(SourceEvent):
    pass


@dataclass(frozen=True, slots=True, repr=False)
class EffectObserved(SourceEvent):
    pass
