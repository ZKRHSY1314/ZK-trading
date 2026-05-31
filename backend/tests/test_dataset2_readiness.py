import json

from app.learning.dataset2_readiness import Dataset2TrainingReadinessService


def _write_dataset2_pack(tmp_path, records):
    pack = tmp_path / "a_share_trading_training_pack_v2"
    (pack / "dataset").mkdir(parents=True)
    (pack / "validation").mkdir()
    (pack / "schemas").mkdir()
    with (pack / "dataset" / "all_training_patterns.jsonl").open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    (pack / "validation" / "check_report.json").write_text(
        json.dumps({"dataset_version": "0.2.0", "status": "PASS"}),
        encoding="utf-8",
    )
    (pack / "validation" / "manifest.json").write_text(
        json.dumps({"status": "PASS"}),
        encoding="utf-8",
    )
    (pack / "schemas" / "pattern_schema.json").write_text(
        json.dumps({"title": "fixture schema"}),
        encoding="utf-8",
    )
    return pack


def _record(**overrides):
    data = {
        "dataset_version": "0.2.0",
        "pattern_id": "FIXTURE_001",
        "pattern_name": "fixture pattern",
        "category": "fixture",
        "source_id": "SRC_FIXTURE",
        "source_document": "fixture.pdf",
        "timeframe": "daily",
        "market_phase": ["low_area"],
        "preconditions": ["clean setup"],
        "observable_features": ["high_volume"],
        "trigger_conditions": ["price and volume confirm"],
        "confirmation_signals": ["follow through"],
        "negative_filters": ["limit up without liquidity"],
        "invalidation_conditions": ["breaks support"],
        "expected_bias": "bullish",
        "action_label": "WAIT_CONFIRMATION",
        "risk_level": "medium",
        "confidence": "medium",
        "software_tags": ["fixture"],
        "rule_logic": "wait for confirmation",
        "evidence_summary": "fixture evidence",
        "training_notes": "fixture notes",
        "stock_code": "SZ000001",
        "signal_date": "2026-05-01",
        "entry_price": 10.0,
        "exit_price": 10.5,
        "forward_return_5d": 0.05,
        "max_favorable_excursion": 0.08,
        "max_adverse_excursion": -0.02,
        "benchmark_return": 0.01,
        "split_tag": "train",
        "model_targets": {
            "direction_bias": "bullish",
            "trade_intent": "simulate_only",
            "allow_live_order": False,
            "requires_backtest": True,
            "requires_human_review_for_real_trade": True,
        },
    }
    data.update(overrides)
    return data


def test_dataset2_readiness_blocks_unclean_training_data(tmp_path):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(
                pattern_id="BAD_RISK",
                risk_level="low_to_medium",
                observable_features=["['big_yang']", "high_volume"],
                evidence_summary="",
                invalidation_conditions=[],
                stock_code=None,
            ),
            _record(pattern_id="GOOD_RISK", action_label="RISK_ALERT", risk_level="high"),
        ],
    )

    data = Dataset2TrainingReadinessService().readiness(source_dir=str(pack))

    assert data["stage"] == "V5.6-P0"
    assert data["status"] == "training_blocked_cleanup_required"
    assert data["quality"]["invalid_risk_level_count"] == 1
    assert data["quality"]["stringified_list_item_count"] == 1
    assert data["quality"]["missing_evidence_counts"]["evidence_summary"] == 1
    assert data["decision"]["can_use_as_rule_knowledge"] is True
    assert data["decision"]["can_start_training_now"] is False
    assert data["safety_summary"]["training_started_now"] is False
    assert data["safety_summary"]["writes_database_now"] is False
    assert data["live_trading_enabled"] is False


def test_dataset2_normalized_preview_cleans_known_weak_labels(tmp_path):
    pack = _write_dataset2_pack(
        tmp_path,
        [
            _record(
                pattern_id="NORMALIZE_ME",
                risk_level="medium_high",
                observable_features=["['big_yang']", "high_volume"],
            )
        ],
    )

    data = Dataset2TrainingReadinessService().normalized_preview(source_dir=str(pack))

    assert data["status"] == "normalized_preview_ready"
    assert data["decision"]["training_started_now"] is False
    assert data["records"][0]["risk_level"] == "high"
    assert data["records"][0]["risk_level_original"] == "medium_high"
    assert data["records"][0]["observable_features"] == ["big_yang", "high_volume"]
    assert "risk_level_normalized" in data["records"][0]["quality_flags"]


def test_dataset2_readiness_api_smoke(client, tmp_path):
    pack = _write_dataset2_pack(tmp_path, [_record()])

    readiness = client.get("/api/learning/dataset2/readiness", params={"source_dir": str(pack)})
    preview = client.post("/api/learning/dataset2/normalized-preview", params={"source_dir": str(pack), "limit": 1})

    assert readiness.status_code == 200
    assert preview.status_code == 200
    assert readiness.json()["decision"]["can_start_training_now"] is False
    assert preview.json()["preview_count"] == 1
    assert preview.json()["safety_summary"]["allow_live_order"] is False
