"""Full retained provenance plus present authority for private lifecycle events."""
from sqlalchemy import select
from . import customer_tables as old, lifecycle_tables as t
from .founder_integrity import CaseProof, read_revision
from .lifecycle_state import reject


def authority(uow, head, component_id, purpose):
    grant = uow.execute(select(t.authorities).where(t.authorities.c.store_id == head['store_id'],
        t.authorities.c.component_id == component_id, t.authorities.c.purpose == purpose).with_for_update()).mappings().one_or_none()
    owner = uow.execute(select(old.principals).where(
        old.principals.c.principal_id == head['owner_principal_id']).with_for_update()).mappings().one_or_none()
    if (grant is None or not grant['enabled'] or owner is None or not owner['enabled']
            or owner['role'] != 'CUSTOMER' or owner['store_id'] != head['store_id']):
        reject(uow, 'FORBIDDEN')
    return grant


class Sources:
    def __init__(self, uow, head, component_id):
        self.uow, self.head, self.component_id = uow, head, component_id
        self.proof = CaseProof(uow, head)

    def read(self, record_id, kinds, *, current_actor=True):
        row = self.proof.revisions.get(record_id)
        if row is None or row['kind'] not in kinds or row['retention_state'] != 'AVAILABLE':
            reject(self.uow)
        result = read_revision(self.uow, row, self.proof)
        if 'content' not in result:
            reject(self.uow)
        actor = self.proof.origin(row)['actor']
        if row['kind'] in {'OPERATION','NOTIFICATION'} and actor['kind']!='SERVICE':
            reject(self.uow,'FORBIDDEN')
        if current_actor:
            if actor['kind'] == 'HUMAN':
                person = self.uow.execute(select(old.principals).where(
                    old.principals.c.principal_id == actor['principal_id']).with_for_update()).mappings().one_or_none()
                if (person is None or not person['enabled'] or person['role'] != actor['role']
                        or person['store_id'] != self.head['store_id']):
                    reject(self.uow, 'FORBIDDEN')
            elif actor['kind'] == 'SERVICE':
                # A saved event name alone is not service authority.
                if actor['component_id'] != self.component_id:
                    reject(self.uow, 'FORBIDDEN')
            # MODEL proves causality only. The consuming SERVICE has already
            # passed current DB authority; no model capability is granted here.
        return row, result['content']

    def bound(self, record_id, work, claim, kinds, *, slot='PRIMARY'):
        row, body = self.read(record_id, kinds)
        binding = self.uow.execute(select(t.sources).where(t.sources.c.record_id == record_id)).mappings().one_or_none()
        expected = dict(case_id=work['case_id'], work_id=work['work_id'], claim_id=claim.claim_id,
            epoch=claim.epoch, generation=claim.generation, input_version=claim.input_version,
            case_version=claim.case_version, source_hash=row['content_sha256'], authority_revision=claim.authority_revision, slot=slot)
        if binding is None or any(binding[key] != value for key, value in expected.items()):
            reject(self.uow)
        if (work['purpose'] not in {'NOTIFICATION','EFFECT'} and row['case_version'] != claim.case_version
                or work['purpose'] in {'NOTIFICATION','EFFECT'} and not claim.case_version <= row['case_version'] <= self.head['case_version']):
            reject(self.uow)
        return row, body, binding
