import pytest
import asyncio
import httpx
from datetime import datetime, timezone

from src.core import CoreListener
from src.adapters.webhook import WebhookAdapter
from tests.integration.datasets import (
    VALID_NOTIFICATION,
    MALFORMED_MISSING_FIELD,
    LARGE_PAYLOAD,
    SCHEMA_V1,
    SCHEMA_V2
)

from fakeredis.aioredis import FakeRedis

class MockPublisher:
    def __init__(self):
        self.published_raw = []
        self.published_canonical = []
        self.redis = FakeRedis()
        
    async def publish_raw(self, payload, fingerprint, tracker):
        self.published_raw.append({"payload": payload, "fingerprint": fingerprint})
        
    async def publish(self, payload, tracker):
        self.published_canonical.append(payload)
        
    async def connect(self):
        pass
        
    async def disconnect(self):
        await self.redis.close()

@pytest.fixture
async def fomo_app(monkeypatch):
    """Fixture to start up the FastAPI app with mocked publisher."""
    mock_pub = MockPublisher()
    
    # Patch the global publisher in core
    import src.core
    monkeypatch.setattr(src.core, "publisher", mock_pub)
    
    listener = CoreListener()
    # Let CoreListener use the mock publisher's redis for deduplication
    listener.deduplicator.redis = mock_pub.redis
    
    webhook_adapter = WebhookAdapter(
        publish_callback=listener.handle_notification,
        host="127.0.0.1",
        port=8000
    )
    
    app = webhook_adapter.app
    # We will test the FastAPI app directly using AsyncClient to avoid
    # spinning up full uvicorn servers during tests, which is standard for FastAPI.
    return app, mock_pub

@pytest.mark.asyncio
async def test_standard_ingestion(fomo_app):
    app, mock_pub = fomo_app
    async with httpx.AsyncClient(app=app, base_url="http://testserver") as client:
        response = await client.post("/webhooks/fomo", json=VALID_NOTIFICATION)
        
        assert response.status_code == 202
        assert response.json() == {"status": "accepted"}
        
        # Check publisher received data
        assert len(mock_pub.published_raw) == 1
        assert len(mock_pub.published_canonical) == 1
        
        canonical = mock_pub.published_canonical[0]
        assert canonical["source_app_id"] == "raydium_tracker"
        assert canonical["event_category"] != "unknown"

@pytest.mark.asyncio
async def test_duplicate_notifications(fomo_app):
    app, mock_pub = fomo_app
    async with httpx.AsyncClient(app=app, base_url="http://testserver") as client:
        # Send same payload twice
        res1 = await client.post("/webhooks/fomo", json=VALID_NOTIFICATION)
        res2 = await client.post("/webhooks/fomo", json=VALID_NOTIFICATION)
        
        assert res1.status_code == 202
        assert res2.status_code == 202
        
        # Raw is written before deduplication currently, wait, deduplication 
        # stops it before publish_canonical! 
        # Check src.core.py to see logic:
        # publish_raw -> deduplicate check -> (returns if duplicate) -> publish
        assert len(mock_pub.published_raw) == 2
        assert len(mock_pub.published_canonical) == 1

@pytest.mark.asyncio
async def test_malformed_payload(fomo_app):
    app, mock_pub = fomo_app
    async with httpx.AsyncClient(app=app, base_url="http://testserver") as client:
        response = await client.post("/webhooks/fomo", json=MALFORMED_MISSING_FIELD)
        
        # Missing required field triggers 422 Unprocessable Entity in FastAPI
        assert response.status_code == 422

@pytest.mark.asyncio
async def test_large_payload(fomo_app, monkeypatch):
    import src.config
    monkeypatch.setattr(src.config.settings, "max_payload_size_bytes", 100000) # Set limit to 100KB for test
    
    app, mock_pub = fomo_app
    async with httpx.AsyncClient(app=app, base_url="http://testserver") as client:
        response = await client.post("/webhooks/fomo", json=LARGE_PAYLOAD)
        
        assert response.status_code == 413

@pytest.mark.asyncio
async def test_schema_changes(fomo_app):
    app, mock_pub = fomo_app
    async with httpx.AsyncClient(app=app, base_url="http://testserver") as client:
        res1 = await client.post("/webhooks/fomo", json=SCHEMA_V1)
        res2 = await client.post("/webhooks/fomo", json=SCHEMA_V2)
        
        assert res1.status_code == 202
        assert res2.status_code == 202
        
        assert len(mock_pub.published_canonical) == 2
        assert mock_pub.published_canonical[0]["source_app_id"] == "legacy_monitor"
        assert mock_pub.published_canonical[1]["source_app_id"] == "v2_monitor"

@pytest.mark.asyncio
async def test_burst_of_events(fomo_app):
    app, mock_pub = fomo_app
    
    import copy
    
    # Send 1000 requests as fast as possible
    async with httpx.AsyncClient(app=app, base_url="http://testserver") as client:
        start_time = datetime.now(timezone.utc)
        
        tasks = []
        for i in range(1000):
            payload = copy.deepcopy(VALID_NOTIFICATION)
            payload["telemetry"]["producer_time"] = i # make them unique so they don't deduplicate
            tasks.append(client.post("/webhooks/fomo", json=payload))
            
        responses = await asyncio.gather(*tasks)
        
        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()
        
        assert all(r.status_code == 202 for r in responses)
        assert len(mock_pub.published_canonical) == 1000
        # Latency check, processing 1000 events locally without uvicorn overhead
        # should easily be under a few seconds.
        assert duration < 5.0

@pytest.mark.asyncio
async def test_delayed_delivery(fomo_app):
    app, mock_pub = fomo_app
    
    async def slow_stream():
        yield b'{"source": "slow",'
        await asyncio.sleep(0.1)
        yield b'"event_type": "test",'
        await asyncio.sleep(0.1)
        yield b'"payload": {}, "telemetry": {}}'
        
    async with httpx.AsyncClient(app=app, base_url="http://testserver") as client:
        response = await client.post("/webhooks/fomo", content=slow_stream(), headers={"content-type": "application/json"})
        assert response.status_code == 202
        assert len(mock_pub.published_canonical) == 1
