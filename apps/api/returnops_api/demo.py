"""Explicit local synthetic demo issuer. Never exposed as an HTTP endpoint."""
import argparse,base64,json,os,secrets,time,sys
from pathlib import Path
import jwt
from .database import build_engine
from .settings import Settings,require_environment_database
from returnops_domain.audit import identifier
from returnops_domain.registry import TrustedRegistry
from returnops_domain.wire import validate

def _private_write(path,value):
    descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(descriptor,'w',encoding='utf-8',newline='\n') as output:
        json.dump(value,output,ensure_ascii=True);output.write('\n')

def _require_private_output_runtime():
    # CPython only applies the private 0700 Windows directory DACL from3.12.4.
    # Fail before inspecting/creating the output or generating any credentials.
    if os.name == "nt" and sys.version_info < (3,12,4):
        raise ValueError("Private demo issuance on Windows requires Python3.12.4 or later.")

def provision(directory,*,store,customer_one,customer_two,founder,order_investigation=False,fixed_proposal=False):
    """Caller explicitly chooses IDs/roles/store; generated credentials stay private."""
    _require_private_output_runtime()
    directory=Path(directory)
    if not directory.is_absolute() or directory.exists(): raise ValueError('Use a new absolute private output directory.')
    people_ids=[customer_one,customer_two,founder]
    if len(set(people_ids))!=3: raise ValueError('Use three distinct demo principal IDs.')
    for value in people_ids+[store]: validate('Id',value)
    settings=Settings.from_environment();require_environment_database(settings.database_url.get_secret_value())
    now=int(time.time());key=secrets.token_bytes(48);issuer='returnops-private-demo';audience='returnops-customer-demo'
    principals=[{'principal_id':value,'role':'FOUNDER' if value==founder else 'CUSTOMER','store_id':store,'enabled':True} for value in people_ids]
    sessions=[{'session_id':identifier('session'),'principal_id':p['principal_id'],'issued_at':now-1,'not_before':now-1,'expires_at':now+899,'revoked':False} for p in principals]
    tokens={row['principal_id']:jwt.encode({'iss':issuer,'aud':audience,'sub':row['principal_id'],'jti':row['session_id'],
        'iat':row['issued_at'],'nbf':row['not_before'],'exp':row['expires_at']},key,algorithm='HS256') for row in sessions}
    directory.mkdir(parents=False,mode=0o700)
    # Files are intentionally written before registration; unknown DB commit does
    # not overwrite/reissue credentials. Inspect that outcome with these same IDs.
    _private_write(directory/'auth.json',{'issuer':issuer,'audience':audience,'signing_key_base64':base64.b64encode(key).decode('ascii')})
    _private_write(directory/'sessions.json',{'principals':principals,'sessions':sessions,'tokens':tokens})
    engine=build_engine(settings)
    try:
        TrustedRegistry(engine).provision(principals,sessions)
        if order_investigation:
            from returnops_domain.investigation_policy import InvestigationPolicy
            from returnops_domain.mock_orders import load_builtin_catalogue
            catalogue=load_builtin_catalogue();policy=InvestigationPolicy(engine)
            policy.configure(store,catalogue=catalogue)
            policy.grant(store,catalogue.metadata.provider_id,can_read=True)
        if fixed_proposal:
            from returnops_domain.proposal_policy import FixedProposalPolicy
            FixedProposalPolicy(engine).grant(store,synthetic_demo=True,enabled=True)
    finally: engine.dispose()

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='command',required=True)
    issue=commands.add_parser('provision');issue.add_argument('--private-dir',required=True)
    for name in ['store','customer-one','customer-two','founder']: issue.add_argument('--'+name,required=True)
    issue.add_argument('--order-investigation',action='store_true',help='Explicitly enable synthetic investigation and grant this store read access.')
    issue.add_argument('--fixed-proposal',action='store_true',help='Explicitly grant this synthetic store the fixed no-model PROPOSAL component only.')
    serve=commands.add_parser('serve');serve.add_argument('--auth-file',required=True);serve.add_argument('--port',type=int,default=8000)
    serve.add_argument('--fixed-proposal',action='store_true',help='Enable the synthetic fixed-proposal worker; this does not grant store authority.')
    serve.add_argument('--founder-decisions',action='store_true',help='Register the Founder decision POST (A2.07); authority still comes only from the server-side registry and grants.')
    serve.add_argument('--model-showcase',action='store_true',help='Enable the advisory A1.06 Coordinator showcase (docs/44); model settings and the key come only from RETURNOPS_MODEL_* environment variables.')
    args=parser.parse_args(argv)
    if args.command=='provision':
        provision(args.private_dir,store=args.store,customer_one=args.customer_one,customer_two=args.customer_two,founder=args.founder,order_investigation=args.order_investigation,fixed_proposal=args.fixed_proposal)
        print('Private synthetic demo registration completed. Credentials are in the explicit private directory; do not share them.')
    else:
        if not Path(args.auth_file).is_absolute() or not 1024<=args.port<=65535: parser.error('Use an absolute private auth file and an unprivileged port.')
        os.environ['RETURNOPS_AUTH_FILE']=args.auth_file
        os.environ['RETURNOPS_FIXED_PROPOSAL_DEMO']='1' if args.fixed_proposal else '0'
        os.environ['RETURNOPS_FOUNDER_DECISIONS']='1' if args.founder_decisions else '0'
        os.environ['RETURNOPS_MODEL_SHOWCASE']='1' if args.model_showcase else '0'
        import uvicorn
        uvicorn.run('returnops_api.main:create_app',factory=True,host='127.0.0.1',port=args.port,access_log=False,log_level='warning')

GENERIC_FAILURE='Demo setup or startup failed; no credentials are printed. Retain the private files to resolve any uncertain registration.'

def cli(argv=None):
    """Run main(); report a configuration or argument error by its own safe sentence, anything else generically."""
    from .settings import ConfigurationError
    reason=None;failed=False
    try: main(argv)
    except (ConfigurationError,ValueError) as error:
        failed=True;message=str(error)
        if message and message.isprintable() and len(message)<=200: reason=message
    except Exception: failed=True
    if failed:
        print(GENERIC_FAILURE if reason is None else 'Demo setup or startup failed: '+reason+' No credentials are printed.')
        return 1
    return 0

if __name__=='__main__':
    raise SystemExit(cli())
