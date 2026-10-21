"""Success-only exact retained Storage multiset; literals are an independent oracle."""
from collections import Counter
from datetime import datetime, timezone
import re
from runner import require as check

DEFAULT_RAW = "  original\ntext\x00🙂 e\u0301 \ud800 \ud83d\ude00  "
DEFAULT_REF = " order\x00\udfff "
SPECIAL_REF = "\x00ORDER\r\n\udfff"
NOW = datetime(2026,9,26,1,2,3,456789,tzinfo=timezone.utc)
TABLES = ('case_records','original_statement_records','original_statement_contents')


def validate_rows(snapshot, cases, statements, contents):
    counts = snapshot['table_counts']
    check(len(counts) == 61 and counts['alembic_version'] == 1 and snapshot['business_rows'] == 15
          and snapshot['customer_test_schemas'] == [] and snapshot['read_only_shared_fence'] is True,
          'Storage final row/snapshot envelope differs')
    check(all(counts[n] == (5 if n in TABLES else 0) for n in counts if n != 'alembic_version'),
          'Expected only exact5 rows in each Storage table and other57 business tables empty')
    check(len(cases) == len(statements) == len(contents) == 5, 'Storage bundle count differs')
    case_map = {r['case_id']:r for r in cases}
    statement_map = {r['statement_id']:r for r in statements}
    content_map = {r['statement_id']:r for r in contents}
    check(len(case_map) == len(statement_map) == len(content_map) == 5, 'Duplicate retained identity')
    for identity,row in case_map.items():
        check(re.fullmatch(r'case_[0-9a-f]{32}', identity) is not None, 'Invalid actual case ID')
        check(row == dict(case_id=identity, owner_principal_id='customer_test', store_id='store_test',
            case_version=1, input_version=1, status='SUBMITTED', created_at=NOW, updated_at=NOW), 'Case metadata differs')
        statement_id = 'statement_'+identity[5:]
        check(statement_map.get(statement_id) == dict(statement_id=statement_id, case_id=identity,
            kind='ORIGINAL', object_version=1, accepted_case_version=1, accepted_input_version=1,
            submitted_at=NOW), 'Statement identity/metadata/relation differs')
    check(set(statement_map) == set(content_map) == {'statement_'+identity[5:] for identity in case_map},
          'Content one-to-one relation differs')
    payloads = []
    for row in contents:
        check(set(row) == {'statement_id','raw_text','original_order_reference','requested_outcome'}
              and row['requested_outcome'] == 'UNSPECIFIED' and type(row['raw_text']) is bytes
              and (row['original_order_reference'] is None or type(row['original_order_reference']) is bytes),
              'Content type, NULL or outcome differs')
        payloads.append((row['raw_text'],row['original_order_reference']))
    raw = DEFAULT_RAW.encode('utf8','surrogatepass')
    expected = Counter({(raw,None):1, (raw,SPECIAL_REF.encode('utf8','surrogatepass')):1,
        (raw,DEFAULT_REF.encode('utf8','surrogatepass')):2, (b'PRIVATE_BODY',b'PRIVATE_ORDER'):1})
    check(Counter(payloads) == expected, 'Exact surrogatepass payload multiset differs')
    def encoded(value):
        if isinstance(value, datetime):
            return {'datetime_utc':value.astimezone(timezone.utc).isoformat()}
        if type(value) is bytes:
            return {'bytes_hex':value.hex()}
        return value
    return dict(status='EXACT_FIVE_RETAINED_BUNDLES_FIFTEEN_BUSINESS_ROWS',
        rows={name:[{k:encoded(v) for k,v in row.items()} for row in sorted(rows,key=lambda r:next(iter(r.values())))]
              for name,rows in zip(TABLES,(cases,statements,contents))},
        payload_multiset=[dict(raw_hex=a.hex(),reference_hex=None if b is None else b.hex(),count=n)
                          for (a,b),n in expected.items()],
        attribution='Two default/default payload instances match repeat_migration and lost_ack[True] as a multiset; individual node-to-UUID attribution unavailable.',
        retained_without_cleanup=True)


def audit(connection, snapshot):
    # Caller already holds the successful snapshot READ ONLY shared fence.
    from sqlalchemy import text
    rows = [[dict(row) for row in connection.execute(text('SELECT * FROM public.'+name+' ORDER BY '+key)).mappings()]
            for name,key in zip(TABLES,('case_id','statement_id','statement_id'))]
    return validate_rows(snapshot,*rows)
