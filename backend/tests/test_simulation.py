from app.simulation.broker import SimulatedBroker
from app.models import SimulationOrder, TradeSide

def test_order_validation(test_db):
    broker = SimulatedBroker(account_name="test")
    # Using the injected test_db config, so it creates tables correctly since the fixture runs first.
    
    order = SimulationOrder(
        symbol="SH600000",
        side=TradeSide.buy,
        price=10.0,
        quantity=100,
        reason="test"
    )
    # This should not raise an exception
    broker.execute(order)
    
    # Test A-share lot size constraint (volume must be multiple of 100)
    order_invalid_lot = SimulationOrder(
        symbol="SH600000",
        side=TradeSide.buy,
        price=10.0,
        quantity=150,
        reason="test"
    )
    
    try:
        broker.execute(order_invalid_lot)
        valid = True
    except ValueError as e:
        valid = False
        assert "100" in str(e) or "lot" in str(e).lower() or "整数倍" in str(e)
    
    assert not valid

