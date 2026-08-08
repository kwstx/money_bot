import pytest
from datetime import datetime, timezone
from src.intelligence.social import (
    SocialSignal,
    CommunityMetrics,
    InfluencerProfile,
    OffChainCatalyst,
    SocialIntelligenceResult,
    SocialIntelligenceEngine
)

def test_social_signal_processing():
    engine = SocialIntelligenceEngine()
    
    raw_data = {
        "platform": "X",
        "id": "tweet_123",
        "author_id": "user_456",
        "author_username": "crypto_whale",
        "content": "Just bought some $DOGE and $SHIB! Huge listing on binance soon.",
        "engagement": {"likes": 5000, "retweets": 1200}
    }
    
    signal = engine.process_social_signal(raw_data)
    assert signal is not None
    assert signal.source_platform == "X"
    assert "DOGE" in signal.tokens_referenced
    assert "SHIB" in signal.tokens_referenced
    
    # Check if a catalyst was detected
    catalysts = list(engine.active_catalysts.values())
    assert len(catalysts) == 1
    assert catalysts[0].event_type == "EXCHANGE_LISTING"
    assert catalysts[0].target_token == "DOGE"  # Based on heuristic of grabbing the first token

def test_community_analysis():
    engine = SocialIntelligenceEngine()
    
    # Generate mock signals
    signals = []
    for i in range(100):
        signals.append(SocialSignal(
            source_platform="Telegram",
            source_id=f"msg_{i}",
            author_id=f"user_{i%5}",  # Only 5 unique users making 100 messages (bot-like)
            content="LFG! Buy now!",
            timestamp=datetime.now(timezone.utc)
        ))
        
    metrics = engine.analyze_community("project_xyz", signals)
    assert metrics.active_participants_count == 5
    assert metrics.bot_probability_score > 0.5  # High probability due to low unique authors

def test_influencer_profile():
    engine = SocialIntelligenceEngine()
    profile = InfluencerProfile(
        influencer_id="inf_1",
        platform="X",
        username="alpha_caller",
        audience_quality_score=0.8
    )
    
    engine.register_influencer(profile)
    assert "alpha_caller" in engine.influencer_profiles

def test_social_intelligence_result():
    engine = SocialIntelligenceEngine()
    
    # Mock some state
    engine.active_catalysts["cat_1"] = OffChainCatalyst(
        event_id="cat_1",
        event_type="MAJOR_NEWS",
        description="Partnership announced",
        target_token="TOKEN_A",
        credibility_score=0.9,
        market_impact_potential=0.8
    )
    
    result = engine.get_social_intelligence("TOKEN_A")
    assert result.target_id == "TOKEN_A"
    assert len(result.active_catalysts) == 1
    assert len(result.actionable_signals) == 1
    assert result.actionable_signals[0]["type"] == "HIGH_IMPACT_CATALYST"
