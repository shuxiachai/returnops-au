"""Independent frozen-schema oracle and meaningful scoped synthetic lookup tests."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import FrozenInstanceError,replace
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType
import json,traceback
import pytest
from jsonschema import Draft202012Validator,FormatChecker
from returnops_domain.canonical import encode_document
from returnops_domain.mock_orders import MockOrderProvider,SyntheticCatalogue,load_builtin_catalogue
from returnops_domain.order_ports import CatalogueRecord,OrderLookupError,OrderReadContext,OrderSourceUnavailable

ROOT=Path(__file__).resolve().parents[2]
SCHEMAS=json.loads((ROOT/'contracts/v1/schemas.json').read_text(encoding='utf-8'))
SERVICE='synthetic_order_reader'

class Resolver:
    def __init__(self):
        self.calls=[];self.context=OrderReadContext('synthetic_case',7,'synthetic_au_store','synthetic_customer_a',SERVICE,'synthetic_commerce',True)
        self.failure=None
    def resolve(self,case_id,input_version):
        self.calls.append((case_id,input_version))
        if self.failure: raise self.failure
        return self.context

class ObservedSource:
    def __init__(self,catalogue):self.catalogue=catalogue;self.calls=0;self.failure=None;self.override=None
    @property
    def metadata(self):return self.catalogue.metadata
    def read_matches(self,context,reference):
        self.calls+=1
        if self.failure:raise self.failure
        return self.override if self.override is not None else self.catalogue.read_matches(context,reference)

@pytest.fixture
def setup():
    resolver=Resolver();source=ObservedSource(load_builtin_catalogue())
    return MockOrderProvider(resolver,source,service_id=SERVICE),resolver,source

@pytest.fixture
def document():
    return json.loads((ROOT/'packages/returnops_domain/order_data/synthetic_orders_v1.json').read_text(encoding='utf-8'))

def query(reference='SYN-1001',version=7):
    result={'case_id':'synthetic_case','input_version':version}
    if reference is not None:result['order_reference']=reference
    return result

def oracle(name,value):
    Draft202012Validator({'$ref':'#/$defs/'+name,'$defs':SCHEMAS['$defs']},format_checker=FormatChecker()).validate(value)

def assert_private(error):
    assert error.__cause__ is None and error.__context__ is None
    rendered=str(error)+repr(error)+''.join(traceback.format_exception(error))
    for marker in ['PRIVATE','secret-path','foreign-owner']:assert marker not in rendered

def test_all_five_results_match_the_frozen_oracle_and_only_match_has_snapshot(setup):
    provider,resolver,source=setup
    results=[provider.lookup(query()),provider.lookup(query('absent-reference')),provider.lookup(query('SYN-CONFLICT'))]
    resolver.context=replace(resolver.context,can_read_orders=False)
    results.append(provider.lookup(query()))
    resolver.context=replace(resolver.context,can_read_orders=True);source.failure=OrderSourceUnavailable()
    results.append(provider.lookup(query()))
    assert [r['status'] for r in results]==['MATCHED','NOT_FOUND','CONFLICT','AUTHORITY_DENIED','PROVIDER_FAILURE']
    for result in results:
        oracle('OrderLookupResult',result)
        assert result['case_id']=='synthetic_case' and result['input_version']==7
        assert ('snapshot' in result)==(result['status']=='MATCHED')
    assert results[0]['snapshot']['retrieved_at']=='2026-09-20T00:00:00Z'

@pytest.mark.parametrize('field',['store_id','owner_principal_id','service_id','provider_id','can_read_orders','dataset_version','source','role'])
def test_wire_authority_or_source_selection_is_rejected_before_resolver(setup,field):
    provider,resolver,source=setup
    request={**query(),field:'PRIVATE'}
    with pytest.raises(OrderLookupError) as error:provider.lookup(request)
    assert error.value.code=='INVALID_REQUEST';assert_private(error.value)
    assert resolver.calls==[] and source.calls==0

@pytest.mark.parametrize('reference',['SYN-1003','SYN-1004','missing-reference'])
def test_foreign_owner_store_and_nonexistent_reference_are_indistinguishable(setup,reference):
    provider,_,_=setup
    assert provider.lookup(query(reference))==provider.lookup(query('another-missing-reference'))

@pytest.mark.parametrize('reference',[None,'syn-1001',' SYN-1001','SYN-1001 ','SYN-1001\n','\x00','\ud800',' '])
def test_reference_matching_is_exact_not_trimmed_or_casefolded(setup,reference):
    provider,resolver,source=setup
    assert provider.lookup(query(reference))['status']=='NOT_FOUND'
    assert len(resolver.calls)==1
    assert source.calls==int(reference is not None)

@pytest.mark.parametrize('version',[7,7.0,Decimal('7.000')])
def test_integral_input_versions_normalize_semantically_without_increment(setup,version):
    provider,resolver,_=setup
    result=provider.lookup(MappingProxyType(query(version=version)))
    assert type(result['input_version']) is int and result['input_version']==7
    assert resolver.calls==[('synthetic_case',7)]

@pytest.mark.parametrize('patch',[{'input_version':True},{'input_version':1.5},{'input_version':float('nan')},
    {'input_version':9007199254740992},{'case_id':'bad\n'},{'order_reference':''},{'order_reference':'x'*121}])
def test_malformed_requests_are_safe_typed_errors_not_business_results(setup,patch):
    provider,resolver,source=setup
    with pytest.raises(OrderLookupError) as error:provider.lookup({**query(),**patch})
    assert error.value.code=='INVALID_REQUEST';assert_private(error.value)
    assert not resolver.calls and not source.calls

def test_revocation_is_fresh_and_provider_permission_is_bound_to_composition(setup):
    provider,resolver,source=setup
    assert provider.lookup(query())['status']=='MATCHED'
    resolver.context=replace(resolver.context,can_read_orders=False)
    assert provider.lookup(query())['status']=='AUTHORITY_DENIED' and source.calls==1
    resolver.context=replace(resolver.context,can_read_orders=True,provider_id='other_provider')
    assert provider.lookup(query())['status']=='AUTHORITY_DENIED' and source.calls==1
    assert len(resolver.calls)==3

@pytest.mark.parametrize('field,value,code',[('case_id','different_case','CONTEXT_MISMATCH'),
 ('input_version',8,'STALE_INPUT'),('service_id','different_service','CONTEXT_MISMATCH')])
def test_mismatched_or_stale_current_context_never_reads_source(setup,field,value,code):
    provider,resolver,source=setup;resolver.context=replace(resolver.context,**{field:value})
    with pytest.raises(OrderLookupError) as error:provider.lookup(query())
    assert error.value.code==code and source.calls==0

@pytest.mark.parametrize('code',['CASE_ACCESS_DENIED','STALE_INPUT','INVALID_CONFIGURATION'])
def test_resolver_failure_is_sanitized_and_never_reads_catalogue(setup,code):
    provider,resolver,source=setup
    try:
        raise RuntimeError('PRIVATE secret-path foreign-owner')
    except RuntimeError as raw:
        try:raise OrderLookupError(code) from raw
        except OrderLookupError as wrapped:resolver.failure=wrapped
    with pytest.raises(OrderLookupError) as error:provider.lookup(query())
    assert error.value.code==(code if code in {'CASE_ACCESS_DENIED','STALE_INPUT'} else 'CONTEXT_UNAVAILABLE')
    assert_private(error.value);assert source.calls==0

def test_unexpected_resolver_exception_has_no_raw_chain(setup):
    provider,resolver,source=setup;resolver.failure=RuntimeError('PRIVATE secret-path foreign-owner')
    with pytest.raises(OrderLookupError) as error:provider.lookup(query())
    assert_private(error.value);assert source.calls==0

def test_source_fault_is_explicit_trusted_injection_not_a_magic_reference(setup):
    provider,resolver,source=setup
    assert provider.lookup(query('PROVIDER_FAILURE'))['status']=='NOT_FOUND'
    source.failure=RuntimeError('PRIVATE secret-path foreign-owner')
    assert provider.lookup(query())=={'case_id':'synthetic_case','input_version':7,'status':'PROVIDER_FAILURE','message':'The synthetic order source is unavailable.'}
    resolver.context=replace(resolver.context,can_read_orders=False)
    calls=source.calls;assert provider.lookup(query())['status']=='AUTHORITY_DENIED' and source.calls==calls

def test_deepcopy_and_frozen_internal_catalogue_isolation(setup,document):
    provider,resolver,source=setup;first=provider.lookup(query());original=deepcopy(first)
    first['snapshot']['line_items'][0]['quantity']=999;first['snapshot']['line_items'].clear();first['input_version']=100
    assert provider.lookup(query())==original
    catalogue=SyntheticCatalogue.from_document(document);document['orders'][0]['snapshot']['line_items'].clear()
    isolated=MockOrderProvider(resolver,catalogue,service_id=SERVICE)
    assert isolated.lookup(query())==original
    with pytest.raises(FrozenInstanceError):catalogue.metadata.dataset_version='changed'
    with pytest.raises(FrozenInstanceError):catalogue._records=()
    with pytest.raises(AttributeError):provider.metadata='changed'

def test_parallel_reads_are_stable_and_independent(setup):
    provider,_,_=setup
    with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(lambda _:provider.lookup(query()),range(64)))
    assert all(value==results[0] for value in results)
    assert len({id(value['snapshot']['line_items']) for value in results})==64

@pytest.mark.parametrize('field,value',[('quantity',0),('quantity',1000),('quantity',True),('unit_price_minor',-1),
 ('unit_price_minor',1.5),('unit_price_minor',True),('unit_price_minor',9007199254740992)])
def test_catalogue_line_quantity_and_price_constraints_fail_closed(document,field,value):
    document['orders'][0]['snapshot']['line_items'][0][field]=value
    with pytest.raises(OrderLookupError) as error:SyntheticCatalogue.from_document(document)
    assert error.value.code=='INVALID_CONFIGURATION';assert_private(error.value)

@pytest.mark.parametrize('mutation',['duplicate_line','duplicate_snapshot','wrong_provider','real_flag','empty','extra','bad_timestamp'])
def test_corrupt_catalogue_fails_closed_instead_of_empty_results(document,mutation):
    if mutation=='duplicate_line':document['orders'][0]['snapshot']['line_items']*=2
    elif mutation=='duplicate_snapshot':document['orders'][1]['snapshot']['snapshot_id']=document['orders'][0]['snapshot']['snapshot_id']
    elif mutation=='wrong_provider':document['orders'][0]['snapshot']['provider_id']='other_provider'
    elif mutation=='real_flag':document['is_synthetic']=False
    elif mutation=='empty':document['orders']=[]
    elif mutation=='extra':document['PRIVATE']='secret-path'
    else:document['orders'][0]['snapshot']['retrieved_at']='PRIVATE'
    with pytest.raises(OrderLookupError) as error:SyntheticCatalogue.from_document(document)
    assert error.value.code=='INVALID_CONFIGURATION';assert_private(error.value)

def test_direct_constructor_cannot_bypass_catalogue_validation(setup):
    _,_,source=setup
    with pytest.raises(OrderLookupError):SyntheticCatalogue(source.metadata,())

def test_source_cannot_return_foreign_or_duplicate_observations(setup):
    provider,resolver,source=setup
    foreign=source.catalogue.read_matches(replace(resolver.context,owner_principal_id='synthetic_customer_b'),'SYN-1003')[0]
    source.override=(foreign,);assert provider.lookup(query())['status']=='PROVIDER_FAILURE'
    normal=source.catalogue.read_matches(resolver.context,'SYN-1001')[0]
    source.override=(normal,normal);assert provider.lookup(query())['status']=='PROVIDER_FAILURE'

def test_new_catalogue_version_preserves_old_instance_and_requires_new_snapshot_version(document):
    old=SyntheticCatalogue.from_document(document);resolver=Resolver();old_provider=MockOrderProvider(resolver,old,service_id=SERVICE)
    original=old_provider.lookup(query());updated=deepcopy(document);updated['dataset_version']='synthetic-orders-v2'
    updated['orders'][0]['snapshot']['line_items'][0]['unit_price_minor']=5000
    with pytest.raises(OrderLookupError):old.replacement(updated)
    updated['orders'][0]['snapshot']['snapshot_version']=2;updated['orders'][0]['snapshot']['retrieved_at']='2026-09-21T00:00:00Z'
    new=old.replacement(updated);new_provider=MockOrderProvider(resolver,new,service_id=SERVICE)
    assert new_provider.lookup(query())['snapshot']['snapshot_version']==2
    assert old_provider.lookup(query())==original
    assert old.metadata.dataset_sha256!=new.metadata.dataset_sha256
    assert new.metadata.dataset_version=='synthetic-orders-v2'

def test_same_generation_cannot_silently_replace_and_owner_cannot_move(document):
    old=SyntheticCatalogue.from_document(document)
    with pytest.raises(OrderLookupError):old.replacement(document)
    changed=deepcopy(document);changed['dataset_version']='synthetic-orders-v2';changed['orders'][0]['owner_principal_id']='foreign_owner'
    with pytest.raises(OrderLookupError):old.replacement(changed)

def test_corrupt_packaged_resource_reports_safe_configuration_failure(monkeypatch):
    import returnops_domain.mock_orders as module
    class Resource:
        def joinpath(self,*args):return self
        def read_bytes(self):raise OSError('PRIVATE secret-path')
    monkeypatch.setattr(module.resources,'files',lambda _:Resource())
    with pytest.raises(OrderLookupError) as error:load_builtin_catalogue()
    assert error.value.code=='INVALID_CONFIGURATION';assert_private(error.value)


def test_lookup_has_no_disk_network_database_or_api_effects(setup,monkeypatch):
    import builtins,os,socket,sys
    provider,_,_=setup
    modules_before=set(sys.modules)
    def forbidden(*args,**kwargs):raise AssertionError("Lookup attempted external IO")
    with monkeypatch.context() as guard:
        guard.setattr(builtins,"open",forbidden)
        guard.setattr(os,"open",forbidden)
        guard.setattr(socket,"create_connection",forbidden)
        guard.setattr(socket.socket,"connect",forbidden)
        assert provider.lookup(query())["status"]=="MATCHED"
    added=set(sys.modules)-modules_before
    assert not any(name.startswith(("returnops_api", "sqlalchemy")) for name in added)


def test_component_import_does_not_load_catalogue_or_schema_resources():
    import subprocess,sys
    probe="""
import importlib.resources
from pathlib import Path
import sys
from unittest.mock import patch
with patch.object(importlib.resources, 'files', side_effect=AssertionError('Import read a package resource')):
    import returnops_domain.mock_orders as component
assert 'returnops_domain.wire' not in sys.modules
assert Path(component.__file__).resolve().is_relative_to(Path.cwd())
from returnops_domain.order_ports import OrderReadContext, OrderLookupError
catalogue=component.load_builtin_catalogue()
class Context:
    def resolve(self,case_id,input_version):
        if case_id!='probe_case': raise OrderLookupError('CASE_ACCESS_DENIED')
        if input_version!=1: raise OrderLookupError('STALE_INPUT')
        return OrderReadContext(case_id,input_version,'synthetic_au_store','synthetic_customer_a','probe_service',catalogue.metadata.provider_id,True)
provider=component.MockOrderProvider(Context(),catalogue,service_id='probe_service')
assert provider.lookup({'case_id':'probe_case','input_version':1,'order_reference':'SYN-1001'})['status']=='MATCHED'
assert not any(name.startswith(('returnops_api','sqlalchemy')) for name in sys.modules)
print('PASS lazy component import')
"""
    result=subprocess.run([sys.executable,"-B","-c",probe],cwd=ROOT,capture_output=True,timeout=10)
    assert result.returncode==0,result.stderr.decode(errors="replace")
    assert result.stdout.strip()==b"PASS lazy component import"


def test_context_bypassed_constructor_is_revalidated(setup):
    provider,resolver,source=setup
    bad=object.__new__(OrderReadContext)
    resolver.context=bad
    with pytest.raises(OrderLookupError) as error:provider.lookup(query())
    assert error.value.code=="CONTEXT_UNAVAILABLE" and source.calls==0
    assert_private(error.value)


def test_source_metadata_cannot_change_in_an_existing_provider(setup,document):
    provider,resolver,source=setup
    document["dataset_version"]="synthetic-orders-v2"
    source.catalogue=source.catalogue.replacement(document)
    assert provider.lookup(query())["status"]=="PROVIDER_FAILURE"
    assert source.calls==0
