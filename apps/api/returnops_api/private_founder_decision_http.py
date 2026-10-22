"""Opt-in trusted composition; construction does not connect or load settings."""
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import FlowError
from returnops_domain.wire import validate
from .customer_authority import CurrentRequestAuthority
from .founder_decision_http import FounderDecisionRequestPorts, OPERATION
from .private_approve import compose_private_approve
from .private_reject import compose_private_reject
from .private_revision import compose_private_revision
from .private_manual import compose_private_manual


def compose_private_founder_decision_http(engine, auth_config):
    """Return a factory bound only to trusted engine/config, never HTTP fields."""
    def request_ports(authorization):
        authority = CurrentRequestAuthority(auth_config, authorization)

        def preflight(case_id):
            # A shared fence for current identity/access only. No business grant,
            # cursor, commit or denial audit. Close before body parsing begins.
            with CustomerUnitOfWork(engine, write=False) as uow:
                actor = authority(uow.connection, 'getSession')
                if actor.role != 'FOUNDER':
                    raise FlowError('FORBIDDEN')
                validate('Id', case_id)
                if authority(uow.connection, OPERATION, case_id) != actor:
                    raise FlowError('UNAUTHENTICATED')
            return None

        return FounderDecisionRequestPorts(
            preflight,
            compose_private_approve(engine, auth_config, authorization),
            compose_private_reject(engine, auth_config, authorization),
            compose_private_revision(engine, auth_config, authorization),
            compose_private_manual(engine, auth_config, authorization),
        )

    return request_ports
