"""Actual retained approval setup; EXECUTION provision is test-only and explicit."""
from copy import deepcopy
from sqlalchemy import select, update
from returnops_api.private_approval_admission import compose_private_approval_admission
from returnops_domain import customer_tables as old, lifecycle_tables as life
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.preview_profile import APPROVAL_COMPONENT
from approve_helpers import ready, approve
from manual_helpers import rows


def guard(engine, identities, name='founder', **options):
    return compose_private_approval_admission(engine, identities.auth_config,
        None if name is None else 'Bearer '+identities.tokens[name], **options)


def provision_execution(engine, identities, *, purpose='EXECUTION', component=APPROVAL_COMPONENT):
    with CustomerUnitOfWork(engine, write=True) as uow:
        row = uow.execute(select(life.authorities).where(
            life.authorities.c.store_id == identities.people['founder']['store_id'],
            life.authorities.c.component_id == component, life.authorities.c.purpose == purpose)).first()
        if row is None:
            uow.execute(life.authorities.insert().values(
                store_id=identities.people['founder']['store_id'], component_id=component,
                purpose=purpose, revision=1, enabled=True))
        uow.commit()


def approved(engine, identities, *, outcome='PASS', execution=True):
    case, action, request = ready(engine, identities, outcome=outcome)
    key = 'admission-original-approval'
    result = approve(engine, identities).accept(case, request, key, 'admission-approval-correlation')
    assert result.status == 'ACCEPTED', result
    work, = [row for row in rows(engine, life.work) if row['case_id'] == case and row['purpose'] == 'EXECUTION']
    if execution:
        provision_execution(engine, identities)
    return dict(case_id=case, expected_case_version=result.receipt['case_version'],
        execution_work_id=work['work_id'], original_approval_key=key,
        candidate_command=deepcopy(action['scope']['commands'][0])), dict(
        case=case, action=action, request=request, result=result, work=work)


def case_row(engine, table, case):
    result, = [row for row in rows(engine, table) if row['case_id'] == case]
    return result


def change(engine, table, clause, **values):
    with CustomerUnitOfWork(engine, write=True) as uow:
        before = dict(uow.execute(select(table).where(clause)).mappings().one())
        assert any(before[name] != value for name, value in values.items())
        assert uow.execute(update(table).where(clause).values(**values)).rowcount == 1
        uow.commit()


def current_history(engine, case, kind):
    result, = [row for row in rows(engine, old.history) if row['case_id'] == case and row['kind'] == kind]
    return result
