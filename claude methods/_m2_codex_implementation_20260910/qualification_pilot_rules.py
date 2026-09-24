"""Pure numerical diagnostics. No I/O, imports of runtime providers, or eligibility grant.

The amount/volume envelope is necessary for common-scope raw traded OHLC,
amount and volume. It does not independently identify absolute currency/share
units, because scaling both amount and volume equally leaves the ratio intact.
"""
from decimal import Decimal, InvalidOperation, localcontext
from datetime import date
import re


def number(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError('not a numeric scalar')
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError('invalid decimal') from exc
    if not result.is_finite():
        raise ValueError('nonfinite number')
    return result


def volume_amount_envelope(rows):
    """Rows have date, low, high, volume, amount. Exact bounds; no fitted tolerance.

    Report multipliers applied to amount/volume. A value of 1 is consistent
    with yuan/share; 0.01 with yuan/hand; 10000 with wan-yuan/share. Passing
    cannot distinguish e.g. yuan/share from wan-yuan/wan-share.
    """
    scales = {'1':Decimal(1), '0.01':Decimal('0.01'), '100':Decimal(100),
              '10000':Decimal(10000), '0.0001':Decimal('0.0001')}
    result = {'rows':len(rows), 'positive_pairs':0, 'zero_zero':[],
              'invalid_rows':[], 'scale_results':{},
              'absolute_units_verified':False, 'vendor_basis_verified':False,
              'eligibility_granted':False}
    checks = {key:{'inside':0,'outside':0,'violations':[]} for key in scales}
    for i,row in enumerate(rows):
        day = str(row.get('date', f'row:{i}'))
        try:
            low,high,volume,amount = (number(row[k]) for k in ('low','high','volume','amount'))
            if low <= 0 or high < low or volume < 0 or amount < 0:
                raise ValueError('invalid range or negative measure')
            if volume == 0 and amount == 0:
                result['zero_zero'].append(day)
                continue
            if volume == 0 or amount == 0:
                raise ValueError('only one of volume/amount is zero')
            result['positive_pairs'] += 1
            with localcontext() as context:
                context.prec = 50
                ratio = amount / volume
                for key,scale in scales.items():
                    check = checks[key]
                    implied = ratio * scale
                    if low <= implied <= high:
                        check['inside'] += 1
                    else:
                        check['outside'] += 1
                        check['violations'].append({'date':day, 'low':str(low),
                            'high':str(high), 'implied_price':str(implied)})
        except (ValueError,KeyError,TypeError) as exc:
            result['invalid_rows'].append({'date':day,'error':str(exc)})
    result['scale_results'] = checks
    result['necessary_envelope_at_scale_1'] = (
        'NOT_OBSERVED' if not result['positive_pairs'] else
        'FAIL' if result['invalid_rows'] or checks['1']['outside'] else 'PASS')
    return result


def compare_adjustments(series):
    """Compare already normalized date->OHLCVA maps without blessing any basis."""
    if set(series) != {'0','1','2'}:
        raise ValueError('exactly the 0/1/2 observations are required')
    dates = set(series['0'])
    if any(set(view) != dates for view in series.values()):
        raise ValueError('adjustment views have different date keys')
    pairs = {}
    for other in ('1','2'):
        price_differences=[]
        measure_differences=[]
        for day in sorted(dates):
            left,right = series['0'][day],series[other][day]
            if any(number(left[k]) != number(right[k]) for k in ('open','high','low','close')):
                price_differences.append(day)
            if any(number(left[k]) != number(right[k]) for k in ('volume','amount')):
                measure_differences.append(day)
        pairs['0_vs_'+other] = {'price_difference_dates':price_differences,
            'volume_amount_difference_dates':measure_differences}
    return {'common_dates':len(dates), 'pairs':pairs,
            'vendor_basis_verified':False, 'eligibility_granted':False}


def cash_forward_relation(series, events):
    """Check every OHLC against independently retained cash implementation facts.

    This is a diagnostic of the fixed vendor contract, not a dividend-adjustment
    implementation or a permission to reconstruct adjusted prices. Events must
    carry an original official document hash and the actual ex-date, not an
    approval date. A result is useful only together with reviewed protocol
    mapping, identity, units and a complete source-specific evidence scope.

    The exact equation being tested is P0(day)-P1(day) = sum(cash after day).
    No tolerance is fitted and no price or event is changed to satisfy it.
    """
    adjustments = compare_adjustments(series)
    dates = sorted(series['0'])
    for day in dates:
        if date.fromisoformat(day).isoformat() != day:
            raise ValueError('date is not canonical ISO')
    if not dates or not events:
        return {'status':'NOT_OBSERVED', 'eligible':False, 'reason':'missing observations or events'}
    seen = set()
    parsed = []
    for event in events:
        ex_date = event['ex_date']
        if date.fromisoformat(ex_date).isoformat() != ex_date or ex_date in seen:
            raise ValueError('duplicate or invalid ex-date')
        seen.add(ex_date)
        cash = number(event['cash_per_share_CNY'])
        if cash <= 0 or not re.fullmatch(r'[0-9a-f]{64}', event.get('document_sha256','')):
            raise ValueError('event requires positive cash and original document hash')
        if ex_date not in dates or ex_date <= dates[0]:
            raise ValueError('event must have observations before and on its ex-date')
        parsed.append((ex_date,cash))
    mismatches = []
    boundaries = []
    for i,day in enumerate(dates):
        expected = sum((cash for ex_date,cash in parsed if day < ex_date), Decimal(0))
        for key in ('open','high','low','close'):
            actual = number(series['0'][day][key])-number(series['1'][day][key])
            if actual != expected:
                mismatches.append({'date':day,'field':key,'expected':str(expected),'actual':str(actual)})
        if day in seen:
            previous = dates[i-1]
            left = number(series['0'][previous]['close'])-number(series['1'][previous]['close'])
            right = number(series['0'][day]['close'])-number(series['1'][day]['close'])
            boundaries.append({'ex_date':day,'previous_observed_date':previous,
                               'observed_cash_step':str(left-right)})
    forward = adjustments['pairs']['0_vs_1']
    backward = adjustments['pairs']['0_vs_2']
    unchanged_measures = not forward['volume_amount_difference_dates'] and not backward['volume_amount_difference_dates']
    distinct_controls = bool(forward['price_difference_dates']) and bool(backward['price_difference_dates'])
    passed = not mismatches and unchanged_measures and distinct_controls
    return {'status':'PASS' if passed else 'FAIL', 'common_dates':len(dates),
            'OHLC_checks':len(dates)*4, 'mismatches':mismatches,
            'events':len(parsed), 'boundaries':boundaries,
            'volume_amount_invariant_across_modes':unchanged_measures,
            'both_adjusted_price_controls_distinct':distinct_controls,
            'eligibility_granted':False,
            'scope':'fixed source contract diagnostic; not a standalone vendor-basis certificate'}


def m1_p4_numeric_consistency(rows):
    """Reproduce frozen M1 P4 numerical bounds under a candidate share/CNY unit.

    This does not independently certify those units. The accepted M1 rule uses
    low*0.98..high*1.02; our additional exact envelope is diagnostic only and
    must not silently replace this frozen gate with a stricter new threshold.
    Zero amount or volume is quarantined by P4, never interpreted as verified.
    """
    quarantined=[]
    contradicted=[]
    for i,row in enumerate(rows):
        day=str(row.get('date',f'row:{i}'))
        try:
            low,high,volume,amount=(number(row[k]) for k in ('low','high','volume','amount'))
        except (ValueError,KeyError,TypeError):
            quarantined.append(day)
            continue
        if amount <= 0 or volume <= 0:
            quarantined.append(day)
            continue
        with localcontext() as context:
            context.prec=50
            ratio=amount/volume
            if not low*Decimal('0.98') <= ratio <= high*Decimal('1.02'):
                contradicted.append(day)
    status=('UNKNOWN' if not rows else 'FAIL' if contradicted else
            'UNKNOWN' if quarantined else 'PASS')
    return dict(status=status,rows=len(rows),contradicted_dates=contradicted,
                quarantined_dates=quarantined,lower_multiplier='0.98',upper_multiplier='1.02',
                absolute_units_verified=False,
                rule_source='claude methods/_m1_closure/acceptance_runner.py:163-215')


def absolute_unit_evidence(rows, host_market, semantics, anchors):
    """Combine separately reviewed source semantics, official anchors and P4.

    The caller must verify the source-artifact hashes and independently replay
    each anchor from its official body and THS raw body. These dictionaries are
    pure numerical inputs, not a replacement for that evidence binding.

    The scale comparison rejects known hand/wan/yi or reciprocal scale mistakes.
    It ranks fixed unit-scale hypotheses by symmetric multiplicative distance;
    it is not a new data-accuracy tolerance, a dtype inference, or proof of
    decimal equality. Small observed differences remain in the output. Neither
    binary32 comparisons nor a conjectured wire format are consulted.
    """
    requirements = {
        'market':host_market in ('USHA','USZA','USTM','USHT'),
        'volume_field':semantics.get('volume_field_id')==13,
        'amount_field':semantics.get('amount_field_id')==19,
        'unscaled_values':semantics.get('plugin_numeric_transform')=='identity',
        'volume_display':semantics.get('volume_display')=='raw_divided_by_share_count_per_unit',
        'stock_share_count':semantics.get('share_count_per_unit',{}).get(host_market)==100,
        'amount_display':semantics.get('amount_display')=='raw_with_magnitude_abbreviation_only',
    }
    checks=[]
    seen=set()
    candidates=tuple(Decimal(value) for value in
        ('0.00000001','0.0001','0.01','1','100','10000','100000000'))
    for anchor in anchors:
        key=(anchor.get('symbol'),anchor.get('date'))
        if key in seen:
            raise ValueError('duplicate unit anchor')
        seen.add(key)
        if not re.fullmatch(r'(SH|SZ|BJ)[0-9]{6}',str(key[0])) or not re.fullmatch(r'[0-9]{8}',str(key[1])):
            raise ValueError('invalid unit anchor identity or date')
        if (anchor.get('official_volume_unit'),anchor.get('official_amount_unit'))!=('share','CNY'):
            raise ValueError('official anchor must establish raw share and CNY units')
        for field in ('reference_sha256','raw_sha256'):
            if not re.fullmatch(r'[0-9a-f]{64}',anchor.get(field,'')):
                raise ValueError('unit anchor needs original official and local body hashes')
        for field in ('volume','amount'):
            comparison=anchor['comparisons'][field]
            official=number(comparison['official_decimal'])
            observed=number(comparison['ths_decimal'])
            if official<=0 or observed<=0:
                raise ValueError('unit anchors need positive actual quantities')
            with localcontext() as context:
                context.prec=50
                scores={str(scale):max(observed*scale/official,official/(observed*scale)) for scale in candidates}
                best=min(scores.values())
                winners=[scale for scale,score in scores.items() if score==best]
                checks.append(dict(symbol=key[0],date=key[1],field=field,
                    official_decimal=str(official),ths_decimal=str(observed),
                    exact_decimal_equal=official==observed,
                    difference_ths_minus_official=str(observed-official),
                    relative_difference=str((observed-official)/official),
                    best_multiplier_candidates=winners,
                    unscaled_uniquely_closest=winners==['1'],
                    comparison_scores={scale:str(score) for scale,score in scores.items()}))
    p4=m1_p4_numeric_consistency(rows)
    # Two independently documented dates span old and recent history in this
    # fixed qualification plan. They do not pretend to sample every security.
    complete=len(seen)>=2 and len(checks)==len(seen)*2
    scale_supported=complete and all(row['unscaled_uniquely_closest'] for row in checks)
    passed=all(requirements.values()) and scale_supported and p4['status']=='PASS'
    return dict(status='PASS' if passed else 'FAIL' if complete else 'UNKNOWN',
        semantic_requirements=requirements,anchor_checks=checks,
        known_unit_scale_hypotheses_support_unscaled=scale_supported,
        p4_numeric_consistency=p4,precision_model_used_for_qualification=False,
        transport_dtype_proven=False,general_data_accuracy_bound_proven=False,
        all_value_accuracy_verified=False,
        decimal_differences_preserved=True,eligibility_granted=False)
