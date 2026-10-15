import pytest
from app.investiq_service import investiq_engine, determine_sector

def test_determine_sector():
    assert determine_sector("HDFCBANK", "HDFC Bank Limited") == "Banking & Finance"
    assert determine_sector("TCS", "Tata Consultancy Services Limited") == "Information Technology"
    assert determine_sector("MARUTI", "Maruti Suzuki India Limited") == "Automobile & Auto Ancillary"
    assert determine_sector("SUNPHARMA", "Sun Pharmaceutical Industries Limited") == "Pharmaceuticals & Healthcare"

def test_investiq_engine_load_and_overview():
    investiq_engine.load_data()
    overview = investiq_engine.get_overview_stats()
    assert overview["total_listed_equities"] > 2000
    assert overview["total_etfs"] > 100
    assert overview["total_smes"] > 100
    assert overview["model_version"] == "investiq-v1"

def test_investiq_rankings_and_filters():
    res = investiq_engine.get_rankings(limit=20)
    assert len(res["data"]) == 20
    assert res["total_count"] > 2000
    assert "Strong" in res["label_counts"]
    assert "Positive" in res["label_counts"]

    # Test sector filter
    res_it = investiq_engine.get_rankings(sector="Information Technology", limit=10)
    for item in res_it["data"]:
        assert item["sector"] == "Information Technology"

    # Test label filter
    res_strong = investiq_engine.get_rankings(growth_label="Strong", limit=10)
    for item in res_strong["data"]:
        assert item["growth_label"] == "Strong"
        assert item["growth_score"] >= 75.0

def test_investiq_company_lookup():
    comp = investiq_engine.get_company("RELIANCE")
    assert comp is not None
    assert comp["symbol"] == "RELIANCE"
    assert "growth_score" in comp
    assert "strengths" in comp
    assert "credit_ratings" in comp

def test_investiq_sectors_summary():
    sectors = investiq_engine.get_sectors_summary()
    assert len(sectors) >= 10
    for sec in sectors:
        assert "sector" in sec
        assert "count" in sec
        assert "avg_growth_score" in sec
        assert "top_stock" in sec
