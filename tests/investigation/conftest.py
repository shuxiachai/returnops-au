"""Reuse the existing schema-isolated PG fixture; issue only private test JWTs."""
from pathlib import Path
import importlib.util
import secrets,time
from dataclasses import dataclass
import jwt,pytest
from returnops_api.security.authentication import AuthConfig
from returnops_api.customer_authority import CurrentRequestAuthority
from returnops_domain.customer_service import CustomerFlow
from returnops_domain.registry import TrustedRegistry
from returnops_domain.investigation_policy import InvestigationPolicy
from returnops_domain.mock_orders import load_builtin_catalogue
from returnops_domain.audit import identifier

spec=importlib.util.spec_from_file_location('investigation_customer_fixture',Path(__file__).parents[1]/'customer/conftest.py')
shared=importlib.util.module_from_spec(spec);spec.loader.exec_module(shared)
flow_engine=shared.flow_engine

@pytest.fixture
def identities(flow_engine):
    now=int(time.time());config=AuthConfig('returnops-tests','returnops-customer-tests',secrets.token_bytes(48),leeway_seconds=0)
    people={name:dict(principal_id='synthetic_'+name,store_id='synthetic_au_store',role='FOUNDER' if name=='founder' else 'CUSTOMER',enabled=True)
        for name in ['customer_a','customer_b','founder']}
    sessions={name:dict(session_id=identifier('session'),principal_id=p['principal_id'],issued_at=now-1,not_before=now-1,expires_at=now+899,revoked=False)
        for name,p in people.items()}
    TrustedRegistry(flow_engine).provision(list(people.values()),list(sessions.values()))
    tokens={name:jwt.encode(dict(iss=config.issuer,aud=config.audience,sub=s['principal_id'],jti=s['session_id'],iat=s['issued_at'],nbf=s['not_before'],exp=s['expires_at']),
        config.signing_key,algorithm='HS256') for name,s in sessions.items()}
    @dataclass(repr=False)
    class Identities:
        auth_config: object
        people: dict
        sessions: dict
        tokens: dict
        def flow(self,name='customer_a',**kwargs): return CustomerFlow(flow_engine,CurrentRequestAuthority(config,'Bearer '+tokens[name]),**kwargs)
    return Identities(config,people,sessions,tokens)

@pytest.fixture
def enabled(flow_engine,identities):
    policy=InvestigationPolicy(flow_engine);policy.configure('synthetic_au_store')
    policy.grant('synthetic_au_store',load_builtin_catalogue().metadata.provider_id,can_read=True)
    return policy
