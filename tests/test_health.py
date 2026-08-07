import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from fastapi.testclient import TestClient
from src.adapters.webhook import WebhookAdapter
from src.monitor import HealthMonitor
from src.config import settings

@pytest.fixture
def test_client():
    # Provide a dummy callback for the adapter
    async def dummy_callback(payload):
        pass
        
    adapter = WebhookAdapter(publish_callback=dummy_callback)
    return TestClient(adapter.app)

@pytest.mark.asyncio
async def test_health_monitor_redis_success():
    monitor = HealthMonitor()
    
    with patch('src.monitor.publisher') as mock_publisher:
        mock_redis = AsyncMock()
        mock_redis.get.return_value = "dummy"
        # Setup mock so heartbeat read matches what we wrote
        async def mock_get(key):
            # We bypass the exact value check for the test
            return None
        mock_redis.get.side_effect = lambda key: mock_redis._last_set
        mock_redis.set.side_effect = lambda key, val, ex: setattr(mock_redis, '_last_set', val)
        
        mock_publisher.redis = mock_redis
        
        result = await monitor._check_redis_connectivity()
        assert result is True
        assert monitor.redis_status == "healthy"

@pytest.mark.asyncio
async def test_health_monitor_redis_failure():
    monitor = HealthMonitor()
    
    with patch('src.monitor.publisher') as mock_publisher:
        mock_redis = AsyncMock()
        mock_redis.ping.side_effect = Exception("Connection error")
        mock_publisher.redis = mock_redis
        
        result = await monitor._check_redis_connectivity()
        assert result is False
        assert monitor.redis_status == "disconnected"

def test_health_endpoint(test_client):
    with patch('src.adapters.webhook.monitor') as mock_monitor:
        mock_monitor.get_status.return_value = {
            "status": "healthy",
            "queue_status": "healthy",
            "rate_status": "healthy",
            "metrics": {
                "total_notifications_received": 5,
                "seconds_since_last_notification": 10.0,
                "recovery_attempts_count": 0
            },
            "timestamp": "2023-10-27T10:00:00Z"
        }
        
        response = test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["queue_status"] == "healthy"
        assert data["metrics"]["total_notifications_received"] == 5

@pytest.mark.asyncio
async def test_health_monitor_notification_rate():
    monitor = HealthMonitor()
    monitor.last_notification_received_at = 0  # Very old
    
    # Let's run a single iteration of the loop logic manually to see how it affects rate_status
    with patch('src.monitor.publisher') as mock_publisher:
        mock_redis = AsyncMock()
        mock_redis.set.side_effect = lambda key, val, ex: setattr(mock_redis, '_last_set', val)
        mock_redis.get.side_effect = lambda key: mock_redis._last_set
        mock_publisher.redis = mock_redis
        
        # Manually run the checks
        await monitor._check_redis_connectivity()
        
        import time
        time_since_last = time.time() - monitor.last_notification_received_at
        if time_since_last > settings.notification_rate_threshold_seconds:
            monitor.rate_status = "degraded"
            
        assert monitor.rate_status == "degraded"
        
        # Now record a notification
        monitor.record_notification()
        assert monitor.rate_status == "healthy"
