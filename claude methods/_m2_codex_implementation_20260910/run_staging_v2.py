"""Offline, exclusively created M2 v2 candidate pair; production byte-read leases."""
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import uuid

import contract_v2 as contract
import staging as old
import staging_v2
import run_actual_staging as guard


def execute(bundle_path, reviewed_sha, boundary, *, test_only=False):
    expected = guard.production_contract()
    require = old._require
    require(guard.check_production(expected)["passed"], "production_preservation_changed_before_run")
    # Reuse full unchanged archive/capture preservation checks, without adopting
    # the deliberately failing v1 qualification verdict.
    prior, _, _, _ = guard.prepare(contract.PINS["qualification_pilot52.json"])
    require(prior["production_preservation"]["passed"], "v1_preservation_check_failed")
    run_id = ("test_v2_" if test_only else "ths_v2_") + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8]
    root = old.ALLOWED_STAGING_PARENT / run_id
    run = staging_v2.StagingRunV2(root, run_id, bundle_path, reviewed_sha)
    boundary.candidates = {p.resolve() for p in run.destinations.values()}
    audit_dir = contract.HERE / "contract_v2_runs" / run_id
    old._safe_existing_chain(audit_dir)
    audit_dir.mkdir(parents=True, exist_ok=False)
    old.StagingRun._json_new(audit_dir / "before.json", dict(production=guard.check_production(expected),
        candidate_files={str(p):p.exists() for p in run.destinations.values()}, qualification_sha256=reviewed_sha,
        input_fingerprint=run._verify_inputs(), production_promoted=False, live_trading=False))
    published_sha = None
    checkpoints = []
    def checkpoint(label):
        run._verify_inputs()
        result = guard.check_production(expected)
        old.StagingRun._json_new(audit_dir / (label + ".json"), result)
        require(result["passed"], "production_changed_" + label)
        checkpoints.append(label)
    try:
        with guard.ProductionReadLocks(expected):
            checkpoint("before_stage")
            candidate = run.stage_from_evidence(reviewed_sha)
            checkpoint("after_stage")
            if test_only:
                reconciliation = run.reconcile()
                connection = run._open_write(run.destinations["trading"])
                connection.execute("UPDATE daily_bar_cache SET amount=amount+1 WHERE symbol='BJ920006' AND trade_date='2023-12-04'")
                connection.commit(); connection.close()
                try:
                    run.reconcile()
                except old.StagingError as exc:
                    require(str(exc) == "v2_stored_prices_or_amounts_differ_from_raw", "unexpected_tamper_rejection")
                else:
                    raise old.StagingError("tampered_amount_not_rejected")
                require(not run.pointer.exists(), "test_pointer_must_not_exist")
                checkpoint("after_tamper_rejection")
                result = dict(status="test_only_tamper_rejected", candidate=candidate, reconciliation=reconciliation,
                    published=False, production_preserved=True, network_requests=0, live_trading=False)
            else:
                receipts = []
                for mode in old.MODES:
                    receipts.append(run.validate(mode, archive_trading=guard.ARCHIVES["trading"],
                        archive_history=guard.ARCHIVES["history"], baseline=guard.ARCHIVE_BASELINE))
                    checkpoint("after_" + mode)
                publication = run.publish(receipts)
                published_sha = old._sha(run.pointer)
                checkpoint("after_publication")
                require(not boundary.denials, "audit_boundary_denial_observed")
                result = dict(status="staging_v2_published", candidate=candidate, publication=publication,
                    pointer_sha256=published_sha, qualification_sha256=reviewed_sha,
                    gate_receipt_sha256=dict(run._receipt_pins), production_preserved=True,
                    production_read_locks="FileAccess.Read FileShare.Read throughout stage, validation and publication",
                    network_requests=0, production_sqlite_connections=0, sqlite_connections=boundary.connections,
                    sqlite_attachments=boundary.attachments, audit_denials=boundary.denials,
                    live_trading=False, production_promoted=False, strict_pit=False,
                    review_performer="Codex self-review; no external-agent independent review claimed")
            result.update(run_id=run_id, run_dir=str(run.run_dir), checkpoints=checkpoints)
            old.StagingRun._json_new(audit_dir / "completion.json", result)
            return result
    except Exception as exc:
        if published_sha is not None and run.pointer.exists() and old._sha(run.pointer) == published_sha:
            require(guard.read_json(run.pointer)["run_id"] == run_id, "foreign_pointer_must_be_preserved")
            run.pointer.unlink()
        old.StagingRun._json_new(audit_dir / "failure.json", dict(reason=str(exc), published=False,
            production_preservation=guard.check_production(expected), audit_denials=boundary.denials,
            live_trading=False, production_promoted=False))
        raise


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--qualification", required=True); ap.add_argument("--sha", required=True)
    ap.add_argument("--execute", action="store_true"); ap.add_argument("--test-tamper", action="store_true")
    args = ap.parse_args()
    boundary = guard.AuditBoundary(); boundary.install()
    if args.execute or args.test_tamper:
        result = execute(Path(args.qualification), args.sha, boundary, test_only=args.test_tamper)
    else:
        bundle, _ = contract.build()
        old._require(old._sha(args.qualification) == args.sha and bundle == guard.read_json(args.qualification), "qualification_not_reproduced")
        result = dict(ready=True, rows=bundle["rows_per_view"], production=guard.check_production(guard.production_contract()),
            network_requests=0, database_connections=0, live_trading=False)
    print(json.dumps(result, ensure_ascii=False, indent=2))
