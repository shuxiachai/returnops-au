"""Frozen HTTP operations against real PG17; request/response bytes stay private."""
import io,json
from pathlib import Path
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from sqlalchemy import select
from returnops_api.main import create_app
from returnops_domain import customer_tables as t
from returnops_domain.intake_processor import IntakeProcessor
from returnops_domain.wire import validate

@pytest.fixture
def client(flow_engine,identities):
    with TestClient(create_app(engine=flow_engine,auth_config=identities.auth_config,enable_processor=False)) as client:
        client.headers['Authorization']='Bearer '+identities.tokens['customer_a']
        yield client

def create(client,key='create-key',message='  Original\x00\ud800\U0001f600e\u0301  '):
    return client.post('/v1/cases',content=json.dumps({'original_message':message},ensure_ascii=True).encode(),headers={'Content-Type':'application/json','Idempotency-Key':key})

def png():
    output=io.BytesIO();Image.new('RGB',(2,2),(4,5,6)).save(output,format='PNG');return output.getvalue()

def assert_error(response,status,code):
    assert response.status_code==status
    validate('ErrorEnvelope',response.json())
    assert response.json()['error']['code']==code
    assert response.headers['X-Correlation-ID']==response.json()['error']['correlation_id']
    assert response.headers['Cache-Control']=='no-store'

def test_all_seven_operations_and_original_bytes(client,flow_engine):
    session=client.get('/v1/session');assert session.status_code==200;validate('Principal',session.json())
    upload=client.post('/v1/evidence',files={'file':('  file.png',png(),'image/png')},data={'description':'untrusted context'},headers={'Idempotency-Key':'upload-key'})
    assert upload.status_code==201,upload.text
    evidence=upload.json();validate('EvidenceAttachment',evidence)
    content=client.get(evidence['content_path']);assert content.status_code==200 and content.content==png()
    assert content.headers['Content-Disposition']=='attachment' and content.headers['Cache-Control']=='no-store'
    accepted=create(client);assert accepted.status_code==201
    body=accepted.json();validate('CustomerCaseView',body);assert body['status']=='SUBMITTED'
    assert body['statements'][0]['raw_text']=='  Original\x00\ud800\U0001f600e\u0301  '
    assert IntakeProcessor(flow_engine).run_once()
    current=client.get('/v1/cases/'+body['case_id']);assert current.status_code==200
    view=current.json();question=view['clarification']
    history=client.get('/v1/cases/'+body['case_id']+'/history',params={'kind':'STATEMENT','cursor':body['collection_windows']['statements']['start_cursor']})
    assert history.status_code==200;validate('CustomerHistoryPage',history.json())
    answer={'expected_case_version':view['case_version'],'question_set_id':question['question_set_id'],
            'answers':[{'question_id':question['questions'][0]['question_id'],'text':'  context\x00\udfff  '}],'evidence_ids':[evidence['evidence_id']]}
    supplemented=client.post('/v1/cases/'+body['case_id']+'/clarifications',content=json.dumps(answer).encode(),headers={'Content-Type':'application/json','Idempotency-Key':'clarify-key'})
    assert supplemented.status_code==202,supplemented.text
    validate('CustomerCaseView',supplemented.json())
    assert supplemented.json()['evidence'][0]['status']=='BOUND'
    assert supplemented.json()['statements'][1]['raw_text']==answer['answers'][0]['text']
    assert IntakeProcessor(flow_engine).run_once()
    assert client.get('/v1/cases/'+body['case_id']).json()['status']=='UNDER_INVESTIGATION'
    assert create(client).json()==body

def test_integer_decimal_and_exponent_replay_semantics(client,flow_engine):
    case=create(client).json()['case_id'];assert IntakeProcessor(flow_engine).run_once()
    view=client.get('/v1/cases/'+case).json();q=view['clarification']
    body={'expected_case_version':2,'question_set_id':q['question_set_id'],'answers':[{'question_id':q['questions'][0]['question_id'],'text':'context'}],'evidence_ids':[]}
    outputs=[]
    for number in ['2.0','2e0','2','20e-1']:
        raw=json.dumps(body,separators=(',',':')).replace('"expected_case_version":2','"expected_case_version":'+number)
        response=client.post('/v1/cases/'+case+'/clarifications',content=raw,headers={'Content-Type':'application/json','Idempotency-Key':'same-answer-key'})
        assert response.status_code==202,response.text
        outputs.append(response.json())
    assert all(value==outputs[0] for value in outputs)
    with flow_engine.connect() as c: assert len(c.execute(select(t.intake_work)).all())==2

@pytest.mark.parametrize('version',['true','1.1','NaN','Infinity','9007199254740991.0000000001','1e999999','1e999999999999999999999999999999999'])
def test_invalid_integer_forms_safe422(client,version):
    case=create(client).json()['case_id']
    raw='{"expected_case_version":'+version+',"question_set_id":"questions_test","answers":[],"evidence_ids":["evidence_test"]}'
    response=client.post('/v1/cases/'+case+'/clarifications',content=raw,headers={'Content-Type':'application/json','Idempotency-Key':'invalid-version-key'})
    assert_error(response,422,'VALIDATION_ERROR')

@pytest.mark.parametrize('raw',[b'{"original_message":"private-marker","original_message":"again"}',b'{"original_message":NaN}',b'{bad private-marker',b'{"original_message":"private-marker","role":"FOUNDER"}'])
def test_malformed_or_forged_json_no_private_error(client,raw):
    response=client.post('/v1/cases',content=raw,headers={'Content-Type':'application/json','Idempotency-Key':'invalid-key'})
    assert_error(response,422,'VALIDATION_ERROR');assert 'private-marker' not in response.text

def test_foreign_and_founder_customer_access(client,identities):
    case=create(client).json()['case_id']
    client.headers['Authorization']='Bearer '+identities.tokens['customer_b']
    assert_error(client.get('/v1/cases/'+case),404,'NOT_FOUND')
    client.headers['Authorization']='Bearer '+identities.tokens['founder']
    assert_error(client.get('/v1/cases/'+case),403,'FORBIDDEN')
    client.headers.pop('Authorization')
    assert_error(client.get('/v1/session',params={'token':identities.tokens['customer_a']}),401,'UNAUTHENTICATED')

def multipart(filename,content,description=b''):
    return (b'--BOUND\r\nContent-Disposition: form-data; name="file"; filename="'+filename+b'"\r\nContent-Type: image/png\r\n\r\n'+content+
        b'\r\n--BOUND\r\nContent-Disposition: form-data; name="description"\r\n\r\n'+description+b'\r\n--BOUND--\r\n')

def test_filename_metadata_unicode_nul_surrogates_and_windows_path_preserved(client):
    filename='C:\\private\\file\x00\ud800\u4e2d.png'
    raw=multipart(filename.replace('\\','\\\\').encode('utf-8','surrogatepass'),png(),'context\x00\udfff'.encode('utf-8','surrogatepass'))
    response=client.post('/v1/evidence',content=raw,headers={'Content-Type':'multipart/form-data; boundary=BOUND','Idempotency-Key':'special-file-key'})
    assert response.status_code==201,response.text
    assert response.json()['filename']==filename and response.json()['description']=='context\x00\udfff'
    download=client.get(response.json()['content_path'])
    assert 'filename' not in download.headers['Content-Disposition']

def test_missing_or_false_content_length_still_caps_stream(client):
    size=10*1024*1024+1
    def chunks():
        yield b'--BOUND\r\nContent-Disposition: form-data; name="file"; filename="too-big.png"\r\nContent-Type: image/png\r\n\r\n'
        for _ in range(size//65536): yield b'x'*65536
        yield b'x'*(size%65536)
        yield b'\r\n--BOUND--\r\n'
    for extra in [{},{'Content-Length':'1'}]:
        response=client.post('/v1/evidence',content=chunks(),headers={'Content-Type':'multipart/form-data; boundary=BOUND','Idempotency-Key':'big-file-key',**extra})
        assert_error(response,413,'REQUEST_TOO_LARGE')

def test_auth_before_body_consumption_and_parser(client,monkeypatch):
    import returnops_api.customer_http as module
    def forbidden(*args): raise AssertionError('Heavy parse must not run')
    monkeypatch.setattr(module,'validate_evidence',forbidden)
    client.headers.pop('Authorization')
    response=client.post('/v1/evidence',content=b'invalid',headers={'Content-Type':'multipart/form-data; boundary=BOUND','Idempotency-Key':'auth-first-key'})
    assert_error(response,401,'UNAUTHENTICATED')

def test_bad_multipart_type_and_content_safe(client):
    response=client.post('/v1/evidence',content=b'private-marker',headers={'Content-Type':'multipart/form-data','Idempotency-Key':'bad-multipart-key'})
    assert_error(response,400,'VALIDATION_ERROR')
    response=client.post('/v1/evidence',files={'file':('private-marker.png',b'invalid','image/png')},headers={'Idempotency-Key':'bad-content-key'})
    assert_error(response,415,'UNSUPPORTED_MEDIA_TYPE');assert 'private-marker' not in response.text

def test_get_queries_and_cursor_context_are_validated(client):
    case=create(client).json()['case_id']
    assert_error(client.get('/v1/cases/'+case+'?unexpected=value'),422,'VALIDATION_ERROR')
    assert_error(client.get('/v1/cases/'+case+'/history?kind=STATEMENT&limit=1&limit=2'),422,'VALIDATION_ERROR')
    assert_error(client.get('/v1/cases/'+case+'/history?kind=STATEMENT&object_version=1'),422,'VALIDATION_ERROR')

def test_only_frozen_customer_founder_reads_and_health_are_registered(client):
    routes={(next(iter(route.methods)),route.path) for route in client.app.routes}
    assert routes=={('GET','/health/live'),('GET','/health/ready'),('GET','/v1/session'),('POST','/v1/evidence'),
       ('GET','/v1/evidence/{evidence_id}/content'),('POST','/v1/cases'),('GET','/v1/cases/{case_id}'),
       ('GET','/v1/cases/{case_id}/history'),('POST','/v1/cases/{case_id}/clarifications'),
       ('GET','/v1/founder/cases'),('GET','/v1/founder/cases/{case_id}'),
       ('GET','/v1/founder/cases/{case_id}/history'),('GET','/v1/founder/cases/{case_id}/audit')}

def test_maximum_legal_escaped_clarification_body_is_accepted(client,flow_engine):
    from returnops_domain.customer_uow import CustomerUnitOfWork
    from returnops_domain.canonical import encode_document
    from returnops_domain.audit import identifier
    from sqlalchemy import update
    case=create(client).json()["case_id"];assert IntakeProcessor(flow_engine).run_once()
    view=client.get("/v1/cases/"+case).json()
    questions=[{"question_id":identifier("question"),"text":"Provide context.","reason":"Structural collection."} for _ in range(20)]
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        uow.execute(update(t.questions).where(t.questions.c.question_set_id==view["clarification"]["question_set_id"]).values(
            questions=encode_document(questions),question_kinds=encode_document({q["question_id"]:"TEXT_RESPONSE" for q in questions})));uow.commit()
    body={"expected_case_version":2,"question_set_id":view["clarification"]["question_set_id"],
          "answers":[{"question_id":q["question_id"],"text":"\U0001f600"*12000} for q in questions],"evidence_ids":[]}
    validate("ClarificationRequest",body)
    raw=json.dumps(body,ensure_ascii=True).encode();assert len(raw)>2*1024*1024
    response=client.post("/v1/cases/"+case+"/clarifications",content=raw,headers={"Content-Type":"application/json","Idempotency-Key":"maximum-answer-key"})
    assert response.status_code==202,response.text[:500]
    assert len(response.json()["statements"])==21
    assert all(s["raw_text"]=="\U0001f600"*12000 for s in response.json()["statements"][1:])

def test_malformed_multipart_parser_logs_contain_no_payload_bytes(client,caplog):
    import logging
    caplog.set_level(logging.DEBUG)
    raw=b"--BOUND\r\nprivate-secret-header@: value\r\n\r\nprivate-message\r\n--BOUND--\r\n"
    response=client.post("/v1/evidence",content=raw,headers={"Content-Type":"multipart/form-data; boundary=BOUND","Idempotency-Key":"private-parse-key"})
    assert_error(response,400,"VALIDATION_ERROR")
    assert "private-secret" not in caplog.text and "private-message" not in caplog.text
    assert "Found invalid character" not in caplog.text and "Expected boundary" not in caplog.text

def test_upload_admission_is_bounded_before_body_read(client):
    slots=client.app.state.upload_slots
    assert slots.acquire(blocking=False) and slots.acquire(blocking=False)
    try:
        response=client.post("/v1/evidence",content=b"unread",headers={"Content-Type":"multipart/form-data; boundary=BOUND","Idempotency-Key":"capacity-key"})
        assert_error(response,503,"INTERNAL_ERROR")
    finally: slots.release();slots.release()
