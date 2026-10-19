"""Explicit internal bootstrap for one synthetic, non-model PROPOSAL producer.

No request, migration, worker or application startup grants this authority.
The purpose and component are fixed here, never supplied by a wire DTO.
"""
from sqlalchemy import select, update
from . import lifecycle_tables as t
from .canonical import digest
from .customer_uow import CustomerUnitOfWork
from .errors import FlowError
from .wire import validate

COMPONENT = 'fixed-synthetic-proposal-v1'
ACTOR = {'kind': 'SERVICE', 'component_id': COMPONENT}
KEY_FIELDS = ('store_id', 'owner_id', 'component_id', 'case_id', 'purpose',
              'input_version', 'generation', 'target_hash')


def stable_id(kind, value):
    return kind + '_' + digest(value, 'fixed-proposal-' + kind + '/v1')


def intent_key(head, state, target_hash):
    return dict(store_id=head['store_id'], owner_id=head['owner_principal_id'],
                component_id=COMPONENT, case_id=head['case_id'], purpose='PROPOSAL',
                input_version=head['input_version'], generation=state['generation'],
                target_hash=target_hash)


class FixedProposalPolicy:
    """Trusted local composition only; explicitly acknowledges a synthetic store."""
    def __init__(self, engine):
        self.engine = engine

    def grant(self, store_id, *, synthetic_demo, enabled):
        validate('Id', store_id)
        if synthetic_demo is not True or type(enabled) is not bool:
            raise FlowError('VALIDATION_ERROR')
        with CustomerUnitOfWork(self.engine, write=True) as uow:
            row = uow.execute(select(t.authorities).where(
                t.authorities.c.store_id == store_id,
                t.authorities.c.component_id == COMPONENT,
                t.authorities.c.purpose == 'PROPOSAL').with_for_update()).mappings().one_or_none()
            revision = 1 if row is None else row['revision'] + 1
            if revision > 9007199254740991:
                raise FlowError('INVALID_STATE')
            values = dict(store_id=store_id, component_id=COMPONENT, purpose='PROPOSAL',
                          enabled=enabled, revision=revision)
            if row is None:
                uow.execute(t.authorities.insert().values(**values))
            else:
                uow.execute(update(t.authorities).where(
                    t.authorities.c.store_id == store_id,
                    t.authorities.c.component_id == COMPONENT,
                    t.authorities.c.purpose == 'PROPOSAL').values(**values))
            uow.commit()
