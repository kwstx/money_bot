import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from src.deduplicator import Deduplicator, LocalTTLCache, normalize_string, normalize_address, normalize_timestamp
from src.config import settings

class TestNormalization(unittest.TestCase):
    def test_normalize_string(self):
        self.assertEqual(normalize_string("  Hello   World  \n"), "hello world")
        self.assertEqual(normalize_string(None), "")
        self.assertEqual(normalize_string(123), "123")

    def test_normalize_address(self):
        self.assertEqual(normalize_address("  0x123AbC  "), "0x123abc")
        self.assertEqual(normalize_address(None), "")

    def test_normalize_timestamp(self):
        self.assertEqual(normalize_timestamp(" 2026-08-07T12:00:00Z "), "2026-08-07t12:00:00z")


class TestLocalTTLCache(unittest.TestCase):
    def test_check_and_set(self):
        cache = LocalTTLCache(ttl_seconds=1)
        
        # First check should succeed (not a duplicate)
        self.assertTrue(cache.check_and_set("key1"))
        
        # Second check should fail (is a duplicate)
        self.assertFalse(cache.check_and_set("key1"))
        
        # Different key should succeed
        self.assertTrue(cache.check_and_set("key2"))

    @patch('src.deduplicator.time.time')
    def test_expiration(self, mock_time):
        cache = LocalTTLCache(ttl_seconds=10)
        
        mock_time.return_value = 100.0
        self.assertTrue(cache.check_and_set("key1"))
        self.assertFalse(cache.check_and_set("key1"))
        
        # Advance time past TTL
        mock_time.return_value = 111.0
        self.assertTrue(cache.check_and_set("key1")) # Should succeed again


class TestDeduplicator(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.dedup = Deduplicator()
        
    def test_extract_stable_fields(self):
        payload = {
            "source": "webhook",
            "event_type": "transfer",
            "payload": {
                "sender_metadata": {"address": "0xABC"},
                "timestamp": "2023-01-01T00:00:00Z",
                "token": "0xTOKEN",
                "recipient": "0xDEF",
                "type": "token_transfer",
                "message": "  Transferred 100 tokens  "
            }
        }
        
        fields = self.dedup.extract_stable_fields(payload)
        self.assertEqual(fields["sender"], "0xabc")
        self.assertEqual(fields["timestamp"], "2023-01-01t00:00:00z")
        self.assertEqual(fields["token_address"], "0xtoken")
        self.assertEqual(fields["wallet_address"], "0xdef")
        self.assertEqual(fields["notification_type"], "token_transfer")
        self.assertEqual(fields["message_content"], "transferred 100 tokens")

    def test_extract_stable_fields_fallback(self):
        # Missing payload should use top level source and event_type
        payload = {
            "source": "api",
            "event_type": "generic_event",
            "payload": None
        }
        
        fields = self.dedup.extract_stable_fields(payload)
        self.assertEqual(fields["sender"], "api")
        self.assertEqual(fields["notification_type"], "generic_event")
        self.assertEqual(fields["timestamp"], "")

    def test_compute_fingerprint_deterministic(self):
        payload1 = {
            "source": "sys", "event_type": "event",
            "payload": {"sender": "Alice", "body": "Hello"}
        }
        # Different order, same keys
        payload2 = {
            "event_type": "event", "source": "sys",
            "payload": {"body": "hello", "sender": "alice"}
        }
        
        fp1 = self.dedup.compute_fingerprint(payload1)
        fp2 = self.dedup.compute_fingerprint(payload2)
        
        self.assertEqual(fp1, fp2)
        
    async def test_is_duplicate_and_store_local_fallback(self):
        fp = "test_fingerprint_local"
        
        # First call should return False (not duplicate)
        is_dup = await self.dedup.is_duplicate_and_store(fp)
        self.assertFalse(is_dup)
        
        # Second call should return True (is duplicate)
        is_dup = await self.dedup.is_duplicate_and_store(fp)
        self.assertTrue(is_dup)

    async def test_is_duplicate_and_store_redis(self):
        mock_redis = AsyncMock()
        # Simulate SET NX returning True (successful set, meaning not a duplicate)
        mock_redis.set.return_value = True 
        
        self.dedup.redis = mock_redis
        
        fp = "test_fingerprint_redis"
        is_dup = await self.dedup.is_duplicate_and_store(fp)
        
        self.assertFalse(is_dup)
        mock_redis.set.assert_called_once()
        
        # Simulate SET NX returning None (key already exists, meaning duplicate)
        mock_redis.set.return_value = None
        is_dup = await self.dedup.is_duplicate_and_store(fp)
        
        self.assertTrue(is_dup)

if __name__ == '__main__':
    unittest.main()
