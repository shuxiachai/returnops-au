"""Read existing SQL mock facts, render in memory; never a provider create API."""
from dataclasses import dataclass
from .customer_uow import CustomerUnitOfWork
from .errors import FlowError
from .label_artifact_sources import (authorize,current_claim,verify_original_label_source_0013,expected_pdf,FILENAME)
from .evidence_validation import validate_evidence

@dataclass(frozen=True,slots=True,repr=False)
class ArtifactTicket:
    work_id: str
    case_id: str
    original_key: str
    claim_id: str
    epoch: int
    recovery_binding_hash: str

@dataclass(frozen=True,slots=True,repr=False)
class ArtifactObservation:
    status: str
    content: bytes | None = None
    safe_code: str | None = None

class CoreLabelArtifactMock:
    def __init__(self,engine,*,uow_factory=CustomerUnitOfWork):
        self.engine,self.uow_factory=engine,uow_factory

    def retrieve_original_label(self,ticket,callback):
        try:
            if type(ticket) is not ArtifactTicket:raise FlowError('VALIDATION_ERROR')
            with self.uow_factory(self.engine,write=False) as uow:
                authorization=authorize(uow,callback,ticket.case_id,store=True)
                row,claim=current_claim(uow,authorization,ticket)
                source=verify_original_label_source_0013(uow,authorization[0],authorization[1],ticket.work_id,ticket.original_key)
                if not source['label']['source_available'] or not source['label']['confirmation_retained']:raise FlowError('INVALID_STATE')
                uow.commit()
            content=expected_pdf(source['fact'])
            checked=validate_evidence(content,FILENAME,'application/pdf')
            if checked.content!=content:raise FlowError('INVALID_STATE')
            # A second fenced transaction checks actual current sources after
            # rendering/parsing; no early snapshot is treated as authority.
            with self.uow_factory(self.engine,write=False) as uow:
                fresh=authorize(uow,callback,ticket.case_id,store=True)
                if fresh!=authorization:raise FlowError('INVALID_STATE')
                fresh_source=verify_original_label_source_0013(uow,fresh[0],fresh[1],ticket.work_id,ticket.original_key)
                if fresh_source!=source or current_claim(uow,fresh,ticket)!=(row,claim):raise FlowError('INVALID_STATE')
                if authorize(uow,callback,ticket.case_id,store=True)!=fresh:raise FlowError('INVALID_STATE')
                current_claim(uow,fresh,ticket)
                uow.commit()
            return ArtifactObservation('FOUND',content)
        except FlowError as error:
            return ArtifactObservation('UNKNOWN' if error.code=='INTERNAL_ERROR' else 'DENIED',safe_code=error.code)
        except Exception:return ArtifactObservation('UNKNOWN')
