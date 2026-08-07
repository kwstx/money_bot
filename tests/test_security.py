import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.schemas import sanitize_text, sanitize_value, RawNotification
from src.config import settings
from src.adapters.webhook import WebhookAdapter

# Helper async mock callback
async def dummy_publish_callback(payload: dict):
    pass

@pytest.fixture
def webhook_client():
    # Setup client using a clean adapter instance
    adapter = WebhookAdapter(publish_callback=dummy_publish_callback)
    return TestClient(adapter.app)

def test_sanitize_text():
    # Test html tag stripping
    assert sanitize_text("<script>alert(1)</script>hello") == "alert(1)hello"
    assert sanitize_text("<div>test</div>") == "test"
    # Test escaping special characters
    assert sanitize_text("hello & welcome < >") == "hello &amp; welcome &lt; &gt;"
    # Test non-string input
    assert sanitize_text(123) == 123

def test_sanitize_value():
    payload = {
        "title": "<b>Bitcoin</b>",
        "nested": {
            "body": "<iframe src='malicious'></iframe>Click here & sign",
            "list_field": ["<p>item 1</p>", "item 2"]
        },
        "number": 42
    }
    cleaned = sanitize_value(payload)
    assert cleaned["title"] == "Bitcoin"
    assert cleaned["nested"]["body"] == "Click here &amp; sign"
    assert cleaned["nested"]["list_field"] == ["item 1", "item 2"]
    assert cleaned["number"] == 42

def test_raw_notification_validation_and_sanitization():
    # Validate and sanitize via Pydantic model validator
    raw = RawNotification(
        source="<b>telegram</b>",
        event_type="<p>new_token</p>",
        payload={"message": "<script>xss</script>hello"}
    )
    assert raw.source == "telegram"
    assert raw.event_type == "new_token"
    assert raw.payload["message"] == "xsshello"

    # Test field length validation
    with pytest.raises(ValueError):
        # too short
        RawNotification(source="", event_type="test", payload={})

    with pytest.raises(ValueError):
        # too long
        RawNotification(source="a" * 300, event_type="test", payload={})

def test_payload_size_limiting(webhook_client, monkeypatch):
    # Set limit to 100 bytes for testing
    monkeypatch.setattr(settings, "max_payload_size_bytes", 100)
    
    # Valid payload within limits
    payload = {
        "source": "telegram",
        "event_type": "info",
        "payload": {"msg": "ok"}
    }
    response = webhook_client.post("/webhooks/fomo", json=payload)
    assert response.status_code == 202

    # Giant payload exceeding 100 bytes
    giant_payload = {
        "source": "telegram",
        "event_type": "info",
        "payload": {"msg": "A" * 500}
    }
    response = webhook_client.post("/webhooks/fomo", json=giant_payload)
    assert response.status_code == 413

def test_api_key_authentication(webhook_client, monkeypatch):
    # Enable authentication
    monkeypatch.setattr(settings, "auth_token", "secret_api_key")
    
    payload = {
        "source": "telegram",
        "event_type": "info",
        "payload": {"msg": "ok"}
    }
    
    # 1. Request with no token header
    response = webhook_client.post("/webhooks/fomo", json=payload)
    assert response.status_code == 401
    
    # 2. Request with incorrect token
    response = webhook_client.post(
        "/webhooks/fomo", 
        json=payload, 
        headers={"X-API-Key": "wrong_key"}
    )
    assert response.status_code == 401
    
    # 3. Request with correct token
    response = webhook_client.post(
        "/webhooks/fomo", 
        json=payload, 
        headers={"X-API-Key": "secret_api_key"}
    )
    assert response.status_code == 202
