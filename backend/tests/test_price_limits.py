import pytest
from app.data.price_limits import infer_board_type, limit_up_threshold

def test_infer_board_type():
    assert infer_board_type("600000", "Test Success") == "main"
    assert infer_board_type("000001", "平安银行") == "main"
    assert infer_board_type("600000", "浦发银行") == "main"
    assert infer_board_type("300001", "特锐德") == "chinext"
    assert infer_board_type("688001", "华兴源创") == "star"
    assert infer_board_type("831039", "国义招标") == "bse"
    assert infer_board_type("000001", "*ST平安") == "st"
    assert infer_board_type("600000", "ST浦发") == "st"

def test_limit_up_threshold():
    assert limit_up_threshold("main") == 9.8
    assert limit_up_threshold("st") == 4.8
    assert limit_up_threshold("chinext") == 19.5
    assert limit_up_threshold("star") == 19.5
    assert limit_up_threshold("bse") == 29.0
    assert limit_up_threshold("unknown") == 9.8
    assert limit_up_threshold("main", {"main": 9.7}) == 9.7
