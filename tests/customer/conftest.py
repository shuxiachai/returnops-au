import os
from datetime import datetime, timezone
from uuid import uuid4
import pytest
from sqlalchemy import create_engine, text
from returnops_api.settings import require_environment_database
from returnops_domain.records import InitialCaseRecord, OriginalStatementRecord, StatementContent, InitialRecordBundle

@pytest.fixture
def customer_engine():
    raw = os.environ.get("DATABASE_URL", "")
    require_environment_database(raw)
    engine = create_engine(raw, hide_parameters=True, echo=False, pool_size=8, max_overflow=2,
                          connect_args={"connect_timeout": 3, "options": "-c statement_timeout=10000"})
    with engine.connect() as connection:
        assert 170000 <= int(connection.execute(text("SHOW server_version_num")).scalar_one()) < 180000
    yield engine
    engine.dispose()

@pytest.fixture
def initial_bundle():
    suffix = uuid4().hex; now = datetime.now(timezone.utc)
    return InitialRecordBundle(InitialCaseRecord("case_"+suffix,"customer_test","store_test",1,1,"SUBMITTED",now,now),
        OriginalStatementRecord("stmt_"+suffix,"case_"+suffix,"ORIGINAL",1,1,1,now),
        StatementContent("stmt_"+suffix,"  preserved\x00\ud800  ","UNSPECIFIED",None))

@pytest.fixture
def flow_engine():
    """A newly created, test-owned schema; never delete the five public baseline rows."""
    from alembic import command
    from alembic.config import Config
    from pathlib import Path
    import re
    raw = os.environ.get("DATABASE_URL", ""); require_environment_database(raw)
    schema = "customer_test_" + uuid4().hex
    assert re.fullmatch(r"customer_test_[0-9a-f]{32}", schema)
    control = create_engine(raw, hide_parameters=True, echo=False)
    with control.begin() as connection:
        assert connection.execute(text("SELECT count(*) FROM pg_namespace WHERE nspname=:name"), {"name":schema}).scalar_one() == 0
        connection.execute(text("CREATE SCHEMA " + schema))
    engine = create_engine(raw, hide_parameters=True, echo=False, pool_size=8, max_overflow=4,
        connect_args={"connect_timeout":3,"options":"-c search_path="+schema+" -c statement_timeout=10000"})
    engine._customer_test_schema = schema
    try:
        config=Config(str(Path(__file__).resolve().parents[2]/"alembic.ini"))
        with engine.begin() as connection:
            config.attributes["connection"]=connection
            command.upgrade(config,"head")
        yield engine
    finally:
        engine.dispose()
        with control.begin() as connection:
            connection.execute(text("DROP SCHEMA " + schema + " CASCADE"))
        control.dispose()

@pytest.fixture
def identities(flow_engine):
    import jwt, secrets, time
    from dataclasses import dataclass, field
    from returnops_domain.registry import TrustedRegistry
    from returnops_api.security.authentication import AuthConfig
    from returnops_api.customer_authority import CurrentRequestAuthority
    from returnops_domain.customer_service import CustomerFlow
    suffix=uuid4().hex; now=int(time.time()); store="store_"+suffix
    config=AuthConfig("returnops-tests","returnops-customer-tests",secrets.token_bytes(48),leeway_seconds=0)
    people={name:{"principal_id":name+"_"+suffix,"role":role,"store_id":store,"enabled":True}
            for name,role in [("customer_a","CUSTOMER"),("customer_b","CUSTOMER"),("founder","FOUNDER")]}
    sessions={name:{"session_id":"session_"+uuid4().hex,"principal_id":p["principal_id"],"issued_at":now-1,"not_before":now-1,"expires_at":now+600,"revoked":False} for name,p in people.items()}
    TrustedRegistry(flow_engine).provision(list(people.values()),list(sessions.values()))
    tokens={name:jwt.encode({"iss":config.issuer,"aud":config.audience,"sub":v["principal_id"],"jti":v["session_id"],"iat":v["issued_at"],"nbf":v["not_before"],"exp":v["expires_at"]},config.signing_key,algorithm="HS256") for name,v in sessions.items()}
    @dataclass(repr=False)
    class PrivateIdentities:
        auth_config: object=field(repr=False)
        people: dict=field(repr=False)
        sessions: dict=field(repr=False)
        tokens: dict=field(repr=False)
        def flow(self,name="customer_a",**kwargs):
            return CustomerFlow(flow_engine,CurrentRequestAuthority(self.auth_config,"Bearer "+self.tokens[name]),**kwargs)
    return PrivateIdentities(config,people,sessions,tokens)
