"""Minimum existing-source checks before making a saved candidate current.

This does not build a packet or call C1/C2. A self-consistent saved bundle is
compared with authoritative customer/order material; retrieval bytes stay intact.
"""
from hashlib import sha256
from sqlalchemy import select
from . import customer_tables as old, investigation_tables as investigation
from .storage import original_statement_records, original_statement_contents
from .customer_service import CustomerFlow
from .founder_queries import _order
from .audit import timestamp
from .canonical import decode_document
from .lifecycle_state import reject


def live_material(uow, head, sources):
    latest = {}
    for row in sources.proof.revisions.values():
        if row['kind'] not in {'STATEMENT','EVIDENCE'}:
            continue
        key=(row['kind'],row['object_id'])
        if key not in latest or latest[key]['object_version']<row['object_version']:
            latest[key]=row
    statements={}
    evidence_history={}
    for (kind,object_id),row in latest.items():
        _,body=sources.read(row['record_id'],{kind},current_actor=False)
        (statements if kind=='STATEMENT' else evidence_history)[object_id]=body
    original=uow.execute(select(original_statement_records).where(
        original_statement_records.c.case_id==head['case_id'])).mappings().one_or_none()
    if original is None:
        reject(uow)
    content=uow.execute(select(original_statement_contents).where(
        original_statement_contents.c.statement_id==original['statement_id'])).mappings().one_or_none()
    expected={'statement_id':original['statement_id'],'kind':'ORIGINAL',
        'raw_text':None if content is None else bytes(content['raw_text']).decode('utf-8','surrogatepass'),
        'requested_outcome':None if content is None else content['requested_outcome'],
        'submitted_at':timestamp(original['submitted_at'])}
    if content is None or statements.get(original['statement_id'])!=expected:
        reject(uow)
    evidence={}
    for row in uow.execute(select(old.evidence).where(old.evidence.c.case_id==head['case_id'])).mappings():
        raw=uow.execute(select(old.evidence_contents.c.body).where(
            old.evidence_contents.c.evidence_id==row['evidence_id'])).scalar_one_or_none()
        if (not row['available'] or row['status']!='BOUND' or row['store_id']!=head['store_id']
                or row['uploader_id']!=head['owner_principal_id'] or raw is None
                or len(raw)!=row['size_bytes'] or sha256(bytes(raw)).hexdigest()!=row['sha256']):
            reject(uow)
        body=CustomerFlow._evidence_view(row)
        if evidence_history.get(row['evidence_id'])!=body:
            reject(uow)
        evidence[row['evidence_id']]=body
    if set(evidence)!=set(evidence_history):
        reject(uow)
    state=uow.execute(select(investigation.state).where(investigation.state.c.case_id==head['case_id'])).mappings().one_or_none()
    if state is None or state['current_projection_id'] is None:
        reject(uow)
    _order(uow,sources.proof,head,state['current_projection_id'])
    projection=uow.execute(select(investigation.projections).where(
        investigation.projections.c.projection_id==state['current_projection_id'])).mappings().one()
    raw=uow.execute(select(investigation.receipt_contents.c.body).where(
        investigation.receipt_contents.c.receipt_id==projection['receipt_id'])).scalar_one()
    lookup=dict(decode_document(raw)['result'])
    lookup['input_version']=head['input_version']
    return original['statement_id'],statements,evidence,lookup,projection['projection_id']


def verify(uow, head, sources, bundle, order_projection_id):
    original,statements,evidence,lookup,current_projection=live_material(uow,head,sources)
    if order_projection_id is None or order_projection_id!=current_projection:
        reject(uow)
    packet=bundle['packet']
    supplied_statements={item['statement_id']:item for item in bundle['statements']}
    supplied_evidence={item['evidence_id']:item for item in bundle['attachments']}
    if (packet['original_statement_id']!=original or supplied_statements!=statements
            or supplied_evidence!=evidence or len(supplied_statements)!=len(bundle['statements'])
            or len(supplied_evidence)!=len(bundle['attachments'])):
        reject(uow)
    # Explicit current-input read projection: the saved original receipt remains
    # on source n; the pinned accepted projection proves it at n+1 <= current m.
    if bundle.get('order_lookup')!=lookup:
        reject(uow)
    retrieval=bundle['retrieval_result']
    passages={item['passage_id']:item for item in retrieval['passages']}
    if len(passages)!=len(retrieval['passages']):
        reject(uow)
    for passage in passages.values():
        if sha256(passage['content'].encode('utf-8')).hexdigest()!=passage['content_sha256']:
            reject(uow)
    checks={item['citation_id']:item for item in bundle['citation_verification']['checks']}
    for citation in packet['citations']:
        passage=passages.get(citation['passage_id'])
        if (passage is None or any(citation[key]!=passage[key] for key in
                ('passage_id','document_id','source_version','corpus_version','content_sha256','location'))
                or checks[citation['citation_id']]['result']!='VALID'):
            reject(uow)
    # The complete original retrieval result, including NO_MATCH and conflicts,
    # stays in the immutable bundle. This guard does not reinterpret support or
    # suppress conflicts on behalf of the independent Risk reviewer.
