"""Offline format-resolution comparison; does not assert the runtime codec.

Reads retained source evidence and a pinned PE file only. Does not load target
assemblies, import the application, use HTTP, or open databases.
"""
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
DLL = Path(r'D:\同花顺软件\同花顺远航版\bin\Hevo.Api.Quotes.dll')
DLL_SHA = '33a69a8c37779f1db3602c6ccd49c9be5e7c4d49cc87c61f7db1278ca7954625'
ANCHOR_SHA = 'fc812f6664a7eb3b2646e20454102cf13f27fc0769d21bfe6107191c1d777fda'
MANTISSA_MAX = 0x07FFFFFF


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pe_rva_bytes(data, rva, count):
    pe = struct.unpack_from('<I', data, 0x3C)[0]
    if data[pe:pe+4] != b'PE\0\0':
        raise ValueError('invalid_pe')
    sections = struct.unpack_from('<H', data, pe+6)[0]
    optional_size = struct.unpack_from('<H', data, pe+20)[0]
    headers = pe + 24 + optional_size
    for i in range(sections):
        at = headers + 40*i
        virtual_size, start, raw_size, raw_at = struct.unpack_from('<IIII', data, at+8)
        if start <= rva and rva+count <= start+raw_size:
            return data[raw_at+rva-start:raw_at+rva-start+count]
    raise ValueError('rva_not_in_backed_section')


def run():
    if sha(DLL) != DLL_SHA:
        raise ValueError('pinned_dll_changed')
    # RVA comes from ECMA-335 FieldRVA metadata, token 0x04002255. Independently
    # map the PE section here instead of trusting the PowerShell decoded output.
    constants = struct.unpack('<8i', pe_rva_bytes(DLL.read_bytes(), 605907, 32))
    if constants != tuple(10**e for e in range(8)):
        raise ValueError('hxlong_multiplier_constants_changed')
    anchor_path = HERE/'unit_anchor_evidence.json'
    if sha(anchor_path) != ANCHOR_SHA:
        raise ValueError('pinned_anchor_changed')
    anchor = json.loads(anchor_path.read_bytes())
    pins = {str(anchor_path):ANCHOR_SHA, str(DLL):DLL_SHA}
    for name, digest in anchor['input_pins'].items():
        if sha(name) != digest:
            raise ValueError('anchor_input_pin_mismatch: '+name)
        pins[name] = digest
    body = json.loads((HERE/'qualification_capture/response_3.bin').read_bytes(),
                      parse_float=Decimal, parse_int=Decimal)
    item = body['data']['items'][0]
    if item['security']['hostFullCode'] != 'USHA600011' or item['security']['fullCode'] != '600011.SH':
        raise ValueError('raw_identity_mismatch')
    observed = {str(p['values']['date_time']):p['values'] for p in item['points']}
    checks = []
    for day in anchor['anchors']:
        for field, comp in day['comparisons'].items():
            reference = Decimal(comp['official_decimal'])
            actual = Decimal(comp['ths_decimal'])
            if observed[day['date']]['transaction_'+field] != actual:
                raise ValueError('anchor_raw_decimal_mismatch')
            quantum = next(Decimal(q) for q in constants if abs(reference) <= MANTISSA_MAX*q)
            delta = actual-reference
            on_grid = actual % quantum == 0 and abs(actual/quantum) <= MANTISSA_MAX
            within_half = abs(delta) <= quantum/2
            # These candidates are unit-conversion hypotheses, not fitted values.
            rejected_scale_candidates = {
                str(scale): abs(actual*scale-reference) > quantum/2
                for scale in [Decimal('0.01'), Decimal(100), Decimal(10000), Decimal(100000000)]
            }
            checks.append({
                'symbol':day['symbol'], 'date':day['date'], 'field':field,
                'official_decimal':str(reference), 'ths_decimal':str(actual),
                'quantum':str(quantum), 'max_abs_difference':str(quantum/2),
                'difference_ths_minus_official':str(delta),
                'ths_on_local_hxlong_grid':on_grid,
                'within_fixed_half_quantum':within_half,
                'same_nearest_grid_point_without_tie_assumption':on_grid and within_half,
                'ths_exact_binary32_value':Decimal.from_float(struct.unpack('>f',struct.pack('>f',float(actual)))[0]) == actual,
                'rejected_ths_multiplier_candidates':rejected_scale_candidates,
            })
    for name in [
        'unit_semantics_static_hxlong_il.txt', 'unit_semantics_static_binary_fields_il.txt',
        'unit_semantics_static_precision_metadata.ps1', 'unit_semantics_static_precision_metadata_success.txt',
        'unit_semantics_static_plugin_il.txt', 'unit_semantics_static_json_number_il.txt',
        'unit_semantics_static_typed_candle_parsers_il.txt', 'unit_semantics_static_gms_field_parser_il.txt',
        'unit_semantics_static_response_v2_il.txt', 'unit_semantics_static_precision_review.md',
        'verify_unit_semantics_static_precision.py',
    ]:
        path = HERE/name
        pins[str(path)] = sha(path)
    if not all(c['same_nearest_grid_point_without_tie_assumption'] for c in checks):
        raise ValueError('anchor_resolution_check_failed')
    if not all(all(c['rejected_ths_multiplier_candidates'].values()) for c in checks):
        raise ValueError('scale_hypothesis_not_discriminated')
    return {
        'schema':'m2.ths.static_unit_precision_review.v1',
        'scope':'two dates, SH600011, raw transaction_volume and transaction_amount',
        'input_pins':pins,
        'local_hxlong_format':{'unsigned_mantissa_max':MANTISSA_MAX,'decimal_multiplier_constants':constants,
            'constant_field_token':'0x04002255','constant_rva':605907,'decoder_method_token':'0x06001A93',
            'decoder_return_type':'System.Double','wire_field_type_is_selected_from_response_header':True},
        'fixed_comparison_rule':'Choose smallest local q=10^e with |official|<=134217727*q; require THS on q grid and absolute difference <= q/2. This is a format-resolution comparison policy, not a claim about the runtime encoder.',
        'checks':checks, 'all_four_format_resolution_comparisons_pass':True,
        'actual_runtime_transport_proven':False,'actual_wire_codec_for_fields_13_19_proven':False,
        'server_encoder_rounding_proven':False,'binary32_source_type_proven':False,
        'general_source_error_bound_proven':False,'all_symbol_eligibility_granted':False,
        'local_mutations':'only exclusive-create requested evidence output',
    }


if __name__ == '__main__':
    output = Path(sys.argv[1]) if len(sys.argv)>1 else HERE/'unit_semantics_static_precision_verification.json'
    result = run()
    with output.open('x',encoding='utf-8') as handle:
        json.dump(result,handle,ensure_ascii=False,indent=2)
    print(json.dumps({'checks':len(result['checks']),'all_four_format_resolution_comparisons_pass':True,
        'sha256':sha(output),'actual_codec_proven':False,'all_symbol_eligibility_granted':False}))
