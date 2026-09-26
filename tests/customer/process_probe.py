"""Child-process probes: credential input via stdin, no token/DSN diagnostics."""
import base64,json,os,sys
from sqlalchemy import create_engine
from returnops_api.security.authentication import AuthConfig
from returnops_api.customer_authority import CurrentRequestAuthority
from returnops_domain.customer_service import CustomerFlow
from returnops_domain.intake_processor import IntakeProcessor
from returnops_domain.audit import identifier

def main():
    value=json.load(sys.stdin)
    schema=value['schema']
    import re
    assert re.fullmatch('customer_test_[0-9a-f]{32}',schema)
    engine=create_engine(os.environ['DATABASE_URL'],hide_parameters=True,echo=False,
        connect_args={'connect_timeout':3,'options':'-c search_path='+schema+' -c statement_timeout=10000'})
    if value['operation']=='create-crash':
        config=AuthConfig(value['issuer'],value['audience'],base64.b64decode(value['key']),leeway_seconds=0)
        flow=CustomerFlow(engine,CurrentRequestAuthority(config,'Bearer '+value['token']))
        flow.create({'original_message':'process synthetic original'},'process-create-key',identifier('corr'))
        os._exit(0)  # admission committed, no receipt delivered to caller
    if value['operation']=='claim-crash':
        claim=IntakeProcessor(engine).claim()
        assert claim is not None
        os._exit(0)
    raise RuntimeError('Unsupported internal test operation')

if __name__=='__main__':
    try:main()
    except Exception:sys.exit(2)
