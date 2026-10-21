"""Passive A2.06/KAN-15/Issue86 PMP06 cost evidence, enabled for one node only.

FR-009 / NFR-003,004,006,007; existing M-A/M-S manual outcome models.
SQL counts mean attempted SQLAlchemy cursor entries on an already bound
Connection AND transaction, excluding setup/unrelated SQL and native COMMIT.
Stage and callback durations are inclusive and overlap; never sum them or
subtract invented overhead. This observer itself adds real overhead.
"""
import json
import os
from threading import Lock, local
from time import monotonic_ns
from types import CodeType, FunctionType


NODE = ('tests/lifecycle/test_founder_pass_manual_late_postgresql.py::'
        'test_PMP06_two_actual_backends_have_one_manual_intent[True]')
ENV = 'RETURNOPS_PMP06_COST_DIAGNOSTIC'
PREFIX = 'RETURNOPS_PMP06_COST_DIAGNOSTIC '
MAXIMUM = (1 << 63) - 1
STAGES = ('create_control', 'validate_control', 'inventory', 'case_proof',
          'notification_descriptor', 'notification_ownership', 'generated_namespace',
          'preview_descriptor', 'preparation_descriptor', 'return_descriptor',
          'label_descriptor', 'artifact_descriptor')
ERRORS = ('OperationalError', 'InterfaceError', 'DBAPIError', 'FlowError',
          'AssertionError', 'AcceptanceOutcomeUnknown')
FLAGS = ('overflow', 'unbound', 'installation', 'clock', 'cleanup',
         'unfinishedcallback', 'record', 'format', 'output', 'original_observer')


def enabled_detail(nodeid):
    if nodeid == NODE and os.environ.get(ENV) == '1':
        return Recorder()
    return None


def _number(value):
    return value if type(value) is int and 0 <= value <= MAXIMUM else None


def _error(error):
    kind = type(error).__name__
    kind = kind if kind in ERRORS else 'OTHER_EXCEPTION'
    try:
        state = getattr(getattr(error, 'orig', None), 'sqlstate', None)
    except BaseException:
        state = None
    if (type(state) is not str or len(state) != 5
            or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789' for c in state)):
        state = None
    return kind, state


def _codes():
    # Resolve only direct code constants of known production functions. Neither
    # callback names, repr, closure contents nor payloads establish identity.
    from returnops_domain.manual_decision import FounderDecisionService
    from returnops_domain.lifecycle_guards import LifecycleGuards
    targets = (
        (FounderDecisionService._new, 'check', None, 'manual_new_check'),
        (FounderDecisionService._replay, 'check', None, 'manual_replay_check'),
        (FounderDecisionService._replay, '<lambda>', '_same_authority', 'manual_replay_authority'),
        (LifecycleGuards.apply, 'notification_final', None, 'notification_final'),
        (LifecycleGuards.apply, '<lambda>', '_before_commit', 'lifecycle_before_commit'),
    )
    result = []
    for owner, name, member, label in targets:
        matches = [code for code in owner.__code__.co_consts
                   if type(code) is CodeType and code.co_name == name
                   and (member is None or member in code.co_names)]
        if len(matches) != 1:
            raise ValueError('Fixed callback code identity unavailable')
        result.append((matches[0], label))
    return result


class Recorder:
    """Bounded, best-effort observer; no own lock crosses an original call."""

    def __init__(self):
        self.lock, self.context = Lock(), local()
        self.rows, self.buckets = [], {}
        self.flags = dict.fromkeys(FLAGS, False)
        self.engine = self.owner = self.events = None
        self.original = self.wrapper = self.listener = None
        self.active = self.listen_attempted = False
        self.codes = []

    def _mark(self, flag):
        # Monotone flags do not acquire any mutex, including error paths.
        try:
            self.flags[flag] = True
        except BaseException:
            pass

    def _safe(self, operation, *args):
        try:
            return operation(*args)
        except BaseException:
            self._mark('record')
            return None

    def _clock(self):
        try:
            value = monotonic_ns()
            if _number(value) is not None:
                return value
        except BaseException:
            pass
        self._mark('clock')
        return None

    def _add(self, row, key, value=1):
        if row[key] > MAXIMUM - value:
            self._mark('overflow')
        row[key] = min(MAXIMUM, row[key] + value)

    def _matched(self, connection):
        if connection is None or connection.engine is not self.engine:
            return None
        current = connection.get_transaction()  # SQLAlchemy local state only.
        return next((row for row in self.rows
                     if row['connection'] is connection and row['transaction'] is current), None)

    def boundary(self, connection, original_row, name, stamp):
        self._safe(self._boundary, connection, original_row, name, stamp)

    def _boundary(self, connection, original_row, name, stamp):
        if not self.active:
            return
        if (connection is None or connection.engine is not self.engine
                or type(original_row) is not dict
                or type(original_row.get('token')) is not int
                or not 1 <= original_row['token'] <= 8):
            if type(original_row) is dict and type(original_row.get('token')) is int and original_row['token'] > 8:
                self._mark('overflow')
            self._mark('unbound')
            return
        if _number(stamp) is None:
            self._mark('clock')
            return
        names = ('fence_call', 'fence_return', 'fence_error', 'commit_call',
                 'native_commit_begin', 'uow_commit_return', 'uow_commit_error')
        if name not in names:
            self._mark('unbound')
            return
        tx = original_row.get('_transaction')
        with self.lock:
            row = next((r for r in self.rows if r['connection'] is connection
                        and r['transaction'] is tx and r['token'] == original_row['token']), None)
            if row is None:
                if tx is None or connection.get_transaction() is not tx:
                    self._mark('unbound')
                    return
                if len(self.rows) == 8:
                    self._mark('overflow')
                    return
                row = dict(token=original_row['token'], connection=connection,
                    transaction=tx, times={}, phase='outside', sql_attempts=0, callbacks=[])
                self.rows.append(row)
            if name in row['times']:
                self._mark('record')
                return
            row['times'][name] = stamp
            row['phase'] = 'body' if name == 'fence_return' else 'outside'

    def stage(self, connection, token, stage, started, duration):
        self._safe(self._stage, connection, token, stage, started, duration)

    def _stage(self, connection, token, stage, started, duration):
        if not self.active:
            return
        with self.lock:
            row = self._matched(connection)
            if row is None or row['token'] != token or stage not in STAGES:
                self._mark('unbound')
                return
            current = getattr(self.context, 'callback', None)
            ordinal = (current[2] if current is not None and current[0] is connection
                       and current[1] is row['transaction'] else None)
            phase = 'callback' if ordinal is not None else row['phase']
            key = (token, phase, ordinal, stage)
            if key not in self.buckets:
                if len(self.buckets) == 256:
                    self._mark('overflow')
                    return
                self.buckets[key] = dict(count=0, inclusive_ns=0, unmeasured_count=0)
            bucket = self.buckets[key]
            self._add(bucket, 'count')
            if _number(started) is None or _number(duration) is None:
                self._mark('clock')
                self._add(bucket, 'unmeasured_count')
            else:
                self._add(bucket, 'inclusive_ns', duration)

    def _sql(self, connection, cursor, statement, parameters, execution_context, executemany):
        # Deliberately never inspect/store statement, parameters or context.
        if self.active:
            self._safe(self._count_sql, connection)

    def _count_sql(self, connection):
        with self.lock:
            row = self._matched(connection)
            if row is not None:
                self._add(row, 'sql_attempts')

    def _register(self, uow, check):
        with self.lock:
            row = self._matched(uow.connection)
            if row is None:
                self._mark('unbound')
                return None
            if len(row['callbacks']) == 8:
                self._mark('overflow')
                return None
            code = check.__code__ if type(check) is FunctionType else None
            label = next((label for known, label in self.codes if code is known), 'unknown')
            if label == 'unknown':
                self._mark('unbound')
            cb = dict(ordinal=len(row['callbacks']) + 1, label=label,
                entered=False, finished=False, entry_ns=None, exit_ns=None,
                inclusive_ns=None, sql_attempts=None, error_type=None, sqlstate=None,
                binding_valid=None)
            row['callbacks'].append(cb)
            return row, cb

    def _enter(self, row, cb):
        stamp = self._clock()
        previous = getattr(self.context, 'callback', None)
        self.context.callback = None
        with self.lock:
            if cb['entered']:
                self._mark('record')
            cb['entered'], cb['entry_ns'] = True, stamp
            cb['binding_valid'] = self._matched(row['connection']) is row
            cb['start_sql'] = row['sql_attempts'] if cb['binding_valid'] else None
            if not cb['binding_valid']:
                self._mark('unbound')
        if cb['binding_valid']:
            self.context.callback = (row['connection'], row['transaction'], cb['ordinal'])
        return previous

    def _leave(self, row, cb, previous, error):
        stamp = self._clock()
        kind, state = _error(error) if error is not None else (None, None)
        # Restore thread context even if recording fails.
        try:
            with self.lock:
                cb.update(finished=True, exit_ns=stamp, error_type=kind, sqlstate=state)
                cb['binding_valid'] = (cb['binding_valid'] is True
                                       and self._matched(row['connection']) is row)
                start = cb['entry_ns']
                if not cb['binding_valid']:
                    self._mark('unbound')
                    cb['inclusive_ns'] = cb['sql_attempts'] = None
                elif stamp is not None and start is not None and stamp >= start:
                    cb['inclusive_ns'] = stamp - start
                else:
                    self._mark('clock')
                if cb['binding_valid']:
                    cb['sql_attempts'] = row['sql_attempts'] - cb['start_sql']
        finally:
            self.context.callback = previous

    def install(self, engine, owner):
        try:
            from sqlalchemy import event
            self.engine, self.owner, self.events = engine, owner, event
            self.codes = _codes()
            original = owner.before_commit
            self.original = original

            def register(uow, check):
                if not self.active or not callable(check) or uow.engine is not engine:
                    return original(uow, check)
                saved = self._safe(self._register, uow, check)
                if saved is None:
                    return original(uow, check)
                row, cb = saved

                def observed(*args, **kwargs):
                    if not self.active:
                        return check(*args, **kwargs)
                    previous = self._safe(self._enter, row, cb)
                    error = None
                    try:
                        return check(*args, **kwargs)
                    except BaseException as caught:
                        error = caught
                        raise  # Preserve original exception object and UoW conversion.
                    finally:
                        self._safe(self._leave, row, cb, previous, error)

                return original(uow, observed)  # Exactly one original registration.

            self.wrapper = register
            owner.before_commit = register
            if owner.before_commit is not register:
                raise RuntimeError('Callback observer installation identity')
            self.listener = self._sql
            self.listen_attempted = True
            event.listen(engine, 'before_cursor_execute', self.listener)
            if not event.contains(engine, 'before_cursor_execute', self.listener):
                raise RuntimeError('SQL observer installation identity')
            self.active = True
        except BaseException:
            self._mark('installation')
            self.cleanup()

    def cleanup(self):
        self.active = False
        try:
            if self.owner is not None and self.wrapper is not None:
                current = self.owner.before_commit
                if current is self.wrapper:
                    self.owner.before_commit = self.original
                elif current is not self.original:
                    self._mark('cleanup')
                if self.owner.before_commit is not self.original:
                    self._mark('cleanup')
        except BaseException:
            self._mark('cleanup')
        if self.listen_attempted:
            self.listen_attempted = False
            try:
                if self.events.contains(self.engine, 'before_cursor_execute', self.listener):
                    self.events.remove(self.engine, 'before_cursor_execute', self.listener)
                if self.events.contains(self.engine, 'before_cursor_execute', self.listener):
                    self._mark('cleanup')
            except BaseException:
                self._mark('cleanup')

    def lines(self, diagnostic):
        # Called only after the original race helper has joined its workers.
        records = []
        known = {}
        if type(diagnostic) is dict:
            for row in diagnostic.get('transactions', [])[:8]:
                if type(row) is dict:
                    known[row.get('token')] = row
            costs = diagnostic.get('costs')
            for source in (diagnostic, costs if type(costs) is dict else {}):
                if any(source.get(key) for key in ('observer_error_count', 'overflow_count',
                       'install_failed', 'cleanup_incomplete')):
                    self._mark('original_observer')
        else:
            self._mark('original_observer')
        for row in self.rows[:8]:
            source = known.get(row['token'], {})
            label, phase, pid = (source.get(key) for key in ('label', 'phase', 'backend_pid'))
            label = label if label in ('holder', 'first', 'second') else 'unknown'
            phase = phase if phase in ('holder', 'accept', 'denial') else 'unknown'
            pid = pid if type(pid) is int and 1 <= pid <= 2147483647 else None
            if pid is None:
                self._mark('unbound')
            times = row['times']
            def span(start, end):
                a, b = times.get(start), times.get(end)
                return b - a if _number(a) is not None and _number(b) is not None and b >= a else None
            records.append(dict(kind='transaction', token=row['token'], label=label,
                phase=phase, backend_pid=pid, sql_attempts=row['sql_attempts'],
                body_ns=span('fence_return', 'commit_call'),
                checks_ns=span('commit_call', 'native_commit_begin')))
            for cb in row['callbacks'][:8]:
                if cb['entered'] and not cb['finished']:
                    self._mark('unfinishedcallback')
                records.append(dict(kind='callback', token=row['token'], **{
                    key: cb[key] for key in ('ordinal', 'label', 'entered', 'finished',
                        'entry_ns', 'exit_ns', 'inclusive_ns', 'sql_attempts', 'error_type', 'sqlstate',
                        'binding_valid')}))
        for (token, phase, ordinal, stage), bucket in list(self.buckets.items())[:256]:
            records.append(dict(kind='stage', token=token, phase=phase,
                callback_ordinal=ordinal, stage=stage, **bucket))
        records.append(dict(kind='coverage', complete=not any(self.flags.values()), **self.flags))
        lines = [PREFIX + json.dumps(record, ensure_ascii=True, separators=(',', ':'),
                                    allow_nan=False) for record in records]
        if len(lines) > 384 or any(len(line) > 1024 or not line.isascii() for line in lines):
            raise ValueError('Diagnostic output bound')
        return lines

    def emit(self, capsys, diagnostic):
        try:
            lines = self.lines(diagnostic)
        except BaseException:
            self._mark('format')
            lines = [PREFIX + '{"kind":"coverage","complete":false,"format":true}']
        try:
            with capsys.disabled():
                for line in lines:
                    print(line, flush=True)
        except BaseException:
            self._mark('output')
