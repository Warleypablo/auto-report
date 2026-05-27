def test_insight_model_importavel():
    from models.insight import Insight
    assert Insight.__tablename__ == "insights"
