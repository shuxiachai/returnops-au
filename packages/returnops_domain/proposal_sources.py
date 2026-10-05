"""Complete retained source inventory, read only inside the authorized fence."""
from dataclasses import dataclass
from hashlib import sha256
from sqlalchemy import select
from . import customer_tables as t
from .founder_codec import digest
from .lifecycle_proposal import live_material
from .lifecycle_sources import Sources
from .lifecycle_state import reject
from .proposal_policy import COMPONENT


@dataclass(frozen=True, repr=False)
class RetainedMaterial:
    original_id: str
    statements: list
    attachments: list
    attachment_bytes: dict
    order_lookup: dict
    projection_id: str

    def fingerprint(self):
        return digest({'original_id': self.original_id, 'statements': self.statements,
                       'attachments': self.attachments, 'order_lookup': self.order_lookup,
                       'projection_id': self.projection_id,
                       'bytes': {key: sha256(value).hexdigest()
                                 for key, value in self.attachment_bytes.items()}})


def read_material(uow, head):
    original, statements, attachments, lookup, projection = live_material(
        uow, head, Sources(uow, head, COMPONENT))
    # live_material compares complete latest DTOs with original storage and all
    # BOUND evidence. Keep bytes in this independent inventory, never in a DTO.
    contents = {}
    for evidence_id, item in attachments.items():
        raw = uow.execute(select(t.evidence_contents.c.body).where(
            t.evidence_contents.c.evidence_id == evidence_id)).scalar_one_or_none()
        if raw is None or len(raw) != item['size_bytes'] or sha256(bytes(raw)).hexdigest() != item['sha256']:
            reject(uow)
        contents[evidence_id] = bytes(raw)
    # CaseProof's sequence order is retained; evidence order is deterministic.
    return RetainedMaterial(original, list(statements.values()),
                            [attachments[key] for key in sorted(attachments)],
                            contents, lookup, projection)
