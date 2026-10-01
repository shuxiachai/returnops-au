"""Independent finite-v2 vectors and unchanged legacy numeric boundaries."""
from decimal import Decimal
import struct
import traceback
import pytest
from returnops_domain import canonical as legacy, founder_codec as finite
from returnops_domain.errors import FlowError
from future_history_fixtures import material


def test_fractional_golden_bytes_and_hash_are_explicit():
    expected=bytes.fromhex('524f5053020000000000000011686973746f72792f66696e6974652d7632723fe999999999999a')
    assert finite.canonical_bytes(.8,finite.HISTORY_DOMAIN) == expected
    assert finite.digest(.8) == '989efe73982c7a370c34c140bd28f07c4440db1105a9455a2feef180b7e4e47d'
    assert finite.decode_document(finite.encode_document(.8)) == .8


@pytest.mark.parametrize('value', [0.0,-0.0,1.0,1e20])
def test_integral_floats_normalize_without_changing_integer_values(value):
    assert finite.encode_document(value) == finite.encode_document(int(value))
    assert type(finite.decode_document(finite.encode_document(value))) is int
    assert finite.decode_document(finite.encode_document(2**53+1)) == 2**53+1
    assert finite.digest(2**53+1) != finite.digest(2**53)
    with pytest.raises(FlowError): legacy.encode_document(value)


@pytest.mark.parametrize('value', [.8,float.fromhex('0x0.0000000000001p-1022'),-1.25,'\ud800','\U0001f600','\ud83d\ude00',{'z':[.8,False],'a':' a\x00\n\udfff '}])
def test_finite_profile_preserves_fraction_and_exact_string_codepoints(value):
    assert finite.decode_document(finite.encode_document(value)) == value
    assert finite.digest('\U0001f600') != finite.digest('\ud83d\ude00')
    assert finite.digest(True) != finite.digest(1)


@pytest.mark.parametrize('value', [float('nan'),float('inf'),float('-inf'),Decimal('.8'),object(),{1:'private'}],ids=['nan','inf','negative-inf','decimal','object','key'])
def test_invalid_number_types_do_not_enter_profile_or_expose_source(value):
    with pytest.raises(FlowError) as error: finite.encode_document(value)
    assert error.value.code == 'INTERNAL_ERROR' and error.value.__cause__ is None and error.value.__context__ is None


@pytest.mark.parametrize('tail', [b'r'+struct.pack('>d',1.0),b'r'+struct.pack('>d',-0.0),b'r'+struct.pack('>d',float('nan')),
    b'r'+struct.pack('>d',float('inf')),b'r\x00',b'x',b's'+(99).to_bytes(8,'big')+b'DO_NOT_LEAK_BODY_VALUE'],ids=['integral-r','negativezero-r','nan-r','inf-r','truncated-r','tag','private-truncated'])
def test_malformed_bytes_have_no_exception_cause_context_or_private_text(tail):
    header=finite.MAGIC+len(finite.BODY_DOMAIN).to_bytes(8,'big')+finite.BODY_DOMAIN.encode()
    try: finite.decode_document(header+tail)
    except FlowError as error:
        assert error.code == 'INTERNAL_ERROR' and error.__cause__ is None and error.__context__ is None
        assert 'DO_NOT_LEAK_BODY_VALUE' not in ''.join(traceback.format_exception(error))
    else: pytest.fail('Malformed profile was accepted')


def test_wrong_profile_trailing_duplicate_and_unsorted_keys_fail():
    encoded=finite.encode_document({'a':1,'b':2})
    key_a=b's'+(1).to_bytes(8,'big')+b'a'
    key_b=b's'+(1).to_bytes(8,'big')+b'b'
    for bad in [encoded+b'n',encoded[:-1],legacy.encode_document({'a':1}),encoded.replace(key_b,key_a),encoded.replace(key_a,key_b,1)]:
        with pytest.raises(FlowError): finite.decode_document(bad)


def test_full_bundle_hash_and_schema_keep_fractional_and_original_content():
    value=material('PROPOSAL','case_synthetic')['content']
    assert value['packet']['confidence'] == .8
    assert finite.validate('HistoricalProposalBundle',value) == value
    first=finite.digest(value)
    value['statements'][0]['raw_text']+='x'
    assert finite.digest(value) != first
    value['packet']['unexpected']='private-value'
    with pytest.raises(FlowError): finite.validate('HistoricalProposalBundle',value)
    with pytest.raises(FlowError): finite.validate('FounderHistoryQuery',{'kind':'PROPOSAL'})


def test_depth_and_schema_integer_bound_are_not_weakened():
    nested=0
    for _ in range(66): nested=[nested]
    with pytest.raises(FlowError): finite.encode_document(nested)
    value=material('PROPOSAL','case_synthetic')['content']
    value['packet']['proposal_version']=2**53
    with pytest.raises(FlowError): finite.validate('HistoricalProposalBundle',value)
