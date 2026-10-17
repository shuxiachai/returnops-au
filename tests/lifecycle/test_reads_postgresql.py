from hashlib import sha256
from sqlalchemy import inspect,text
from returnops_api.customer_authority import CurrentRequestAuthority
from returnops_domain.founder_service import FounderQueries
from synthetic_sources import ready,proposal


def fingerprint(engine):
    with engine.connect() as connection:
        return {name:sha256(repr(sorted((tuple(row) for row in connection.execute(text('SELECT * FROM "'+name+'"'))),key=repr)).encode('utf-8','surrogatepass')).hexdigest()
            for name in inspect(connection).get_table_names() if not name.startswith('founder_')}


def test_founder_current_proposal_and_all_four_reads_do_not_advance_lifecycle(flow_engine,identities,enabled):
    original=ready(flow_engine,identities);case=original['case_id'];proposal(flow_engine,identities,case)
    before=fingerprint(flow_engine)
    reader=FounderQueries(flow_engine,CurrentRequestAuthority(identities.auth_config,'Bearer '+identities.tokens['founder']))
    detail=reader.read('getFounderCase',case).body
    assert detail['current_proposal']['proposal_version']==1 and detail['status']=='RISK_REVIEW'
    reader.read('listFounderCases')
    reader.read('listFounderCaseHistory',case,{'kind':'PROPOSAL'})
    reader.read('listCaseAudit',case)
    assert fingerprint(flow_engine)==before
