"""F.05/F.06 Founder reads on F.03 current authority and the existing global fence."""
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from . import customer_tables as t
from .customer_service import ResponseResult
from .customer_uow import CustomerUnitOfWork
from .errors import FlowError, AcceptanceOutcomeUnknown
from . import founder_queries as queries
from .analytics_queries import analytics
from .wire import validate


class FounderQueries:
    def __init__(self, engine, authority, *, clock=lambda: datetime.now(timezone.utc),
                 snapshot_ttl=900, uow_factory=CustomerUnitOfWork, facts_provider=None):
        if type(snapshot_ttl) is not int or not 1 <= snapshot_ttl <= 900:
            raise FlowError()
        if facts_provider is not None and not callable(facts_provider):
            raise FlowError()
        self.engine, self.authority, self.clock = engine, authority, clock
        self.snapshot_ttl, self.uow_factory = snapshot_ttl, uow_factory
        self.facts_provider = facts_provider

    def _authorize(self, uow, operation, case_id):
        actor = self.authority(uow.connection, 'getSession')
        if actor.role != 'FOUNDER':
            raise FlowError('FORBIDDEN')
        if case_id is not None:
            validate('Id', case_id)
        current = self.authority(uow.connection, operation, case_id)
        if current != actor:
            raise FlowError('UNAUTHENTICATED')
        return current

    def read(self, operation, case_id=None, query=None):
        if operation == 'getFounderAnalytics' and case_id is None:
            return self._analytics(query)
        if operation not in {'listFounderCases', 'getFounderCase', 'listFounderCaseHistory', 'listCaseAudit'}:
            raise FlowError('FORBIDDEN')
        try:
            # Cursor/encoding writes require the exclusive fence from the start;
            # do not acquire a shared fence and upgrade it later.
            with self.uow_factory(self.engine, write=True) as uow:
                actor = self._authorize(uow, operation, case_id)
                query = query() if callable(query) else ({} if query is None else query)
                now = self.clock()
                if now.utcoffset() is None:
                    raise FlowError()
                if operation == 'listFounderCases':
                    result, snap = queries.list_cases(uow, actor, query, now, self.snapshot_ttl)
                else:
                    head = uow.execute(select(t.case_heads).where(t.case_heads.c.case_id == case_id)).mappings().one()
                    if operation == 'getFounderCase':
                        if query != {}:
                            raise FlowError('VALIDATION_ERROR')
                        result, snap = queries.case_view(uow, actor, head, now, self.snapshot_ttl, self.facts_provider)
                    elif operation == 'listFounderCaseHistory':
                        result, snap = queries.history_page(uow, actor, head, query, now, self.snapshot_ttl)
                    else:
                        result, snap = queries.audit_page(uow, actor, head, query, now, self.snapshot_ttl)
                # Reauthenticate from current DB identity with fresh wall time;
                # also recheck every current resource emitted by a list page.
                if self._authorize(uow, operation, case_id) != actor:
                    raise FlowError('UNAUTHENTICATED')
                if operation == 'listFounderCases':
                    for item in result['items']:
                        if self._authorize(uow, 'getFounderCase', item['case_id']) != actor:
                            raise FlowError('UNAUTHENTICATED')
                if snap['expires_at'] <= self.clock():
                    raise FlowError('INVALID_STATE')
                uow.commit()
                return ResponseResult(200, result)
        except (SQLAlchemyError, AcceptanceOutcomeUnknown):
            pass
        raise FlowError() from None

    def _analytics(self, query):
        try:
            # Aggregates write no snapshot/cursor, so the shared fence suffices.
            with self.uow_factory(self.engine, write=False) as uow:
                actor = self._authorize(uow, 'getFounderAnalytics', None)
                query = query() if callable(query) else ({} if query is None else query)
                result = analytics(uow, actor, query, self.clock())
                if self._authorize(uow, 'getFounderAnalytics', None) != actor:
                    raise FlowError('UNAUTHENTICATED')
                uow.commit()
                return ResponseResult(200, result)
        except (SQLAlchemyError, AcceptanceOutcomeUnknown):
            pass
        raise FlowError() from None
