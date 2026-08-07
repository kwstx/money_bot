import hashlib
import json
import logging
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional
from redis.asyncio import Redis

from .config import settings

logger = logging.getLogger(__name__)

class LocalTTLCache:
    """
    A simple thread-safe, in-memory TTL cache for fallback deduplication.
    """
    def __init__(self, ttl_seconds: int, max_size: int = 10000):
        self.ttl = ttl_seconds
        self.max_size = max_size
        self.cache: OrderedDict[str, float] = OrderedDict()

    def _cleanup(self):
        now = time.time()
        while self.cache:
            first_key = next(iter(self.cache))
            if self.cache[first_key] < now:
                self.cache.popitem(last=False)
            else:
                break

    def check_and_set(self, key: str) -> bool:
        """
        Returns True if the key was successfully set (meaning it's NOT a duplicate).
        Returns False if the key already exists and hasn't expired (meaning it IS a duplicate).
        """
        self._cleanup()
        now = time.time()
        
        if key in self.cache:
            if self.cache[key] >= now:
                return False
            else:
                self.cache.pop(key)
        
        if len(self.cache) >= self.max_size:
            self.cache.popitem(last=False)
            
        self.cache[key] = now + self.ttl
        return True


def normalize_string(val: Any) -> str:
    if val is None:
        return ""
    return " ".join(str(val).strip().lower().split())


def normalize_address(val: Any) -> str:
    if val is None:
        return ""
    return str(val).strip().lower()


def normalize_timestamp(val: Any) -> str:
    if val is None:
        return ""
    return str(val).strip().lower()


def extract_value(data: Dict[str, Any], keys: List[str]) -> Optional[Any]:
    for key in keys:
        if "." in key:
            parts = key.split(".")
            val = data
            for part in parts:
                if isinstance(val, dict):
                    val = val.get(part)
                else:
                    val = None
                    break
            if val is not None:
                return val
        else:
            val = data.get(key)
            if val is not None:
                return val
    return None


class Deduplicator:
    """
    Computes deterministic fingerprints for notifications and checks against
    a high-speed cache to prevent duplicate processing.
    """
    
    def __init__(self, redis_client: Optional[Redis] = None):
        self.redis = redis_client
        self.local_cache = LocalTTLCache(ttl_seconds=settings.dedup_cache_ttl)

    def extract_stable_fields(self, notification_dict: dict) -> dict:
        source = notification_dict.get("source") or ""
        top_event_type = notification_dict.get("event_type") or ""
        
        payload = notification_dict.get("payload") or {}
        if not isinstance(payload, dict):
            payload = {}
            
        sender = extract_value(payload, [
            "sender", "sender_id", "from", "sender_address", 
            "sender_metadata.sender", "sender_metadata.address", 
            "sender_metadata.id"
        ])
        if not sender:
            sender = source

        timestamp = extract_value(payload, ["timestamp", "created_at", "time", "date", "datetime"])
        
        token_address = extract_value(payload, [
            "token_address", "tokenAddress", "token", "mint", 
            "token_mint", "referenced_token_address"
        ])
        
        wallet_address = extract_value(payload, [
            "wallet_address", "walletAddress", "wallet", "user_address", 
            "recipient", "referenced_wallet_address"
        ])
        
        notification_type = extract_value(payload, ["notification_type", "type"])
        if not notification_type:
            notification_type = top_event_type
            
        message_content = extract_value(payload, ["body", "message", "content", "text", "description", "title"])
        
        return {
            "sender": normalize_address(sender) if sender else "",
            "timestamp": normalize_timestamp(timestamp) if timestamp else "",
            "token_address": normalize_address(token_address) if token_address else "",
            "wallet_address": normalize_address(wallet_address) if wallet_address else "",
            "notification_type": normalize_string(notification_type) if notification_type else "",
            "message_content": normalize_string(message_content) if message_content else ""
        }

    def compute_fingerprint(self, notification_dict: dict) -> str:
        """
        Computes a deterministic SHA-256 fingerprint from the notification payload.
        """
        stable_fields = self.extract_stable_fields(notification_dict)
        serialized = json.dumps(stable_fields, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    async def is_duplicate_and_store(self, fingerprint: str) -> bool:
        """
        Checks if the fingerprint exists in the cache. If not, stores it.
        Returns True if it's a duplicate, False otherwise.
        """
        if not settings.dedup_enabled:
            return False

        key = f"{settings.dedup_prefix}{fingerprint}"
        
        # Try Redis first if available
        if self.redis:
            try:
                # SET NX EX sets the key only if it does not exist, with an expiration
                # returns True if set (new fingerprint), None if already existed (duplicate)
                success = await self.redis.set(
                    key, 
                    "1", 
                    ex=settings.dedup_cache_ttl, 
                    nx=True
                )
                return not success
            except Exception as e:
                logger.warning(f"Redis deduplication failed, error: {e}")
                if not settings.dedup_use_local_fallback:
                    # If fallback disabled, allow processing to prevent halting ingestion
                    return False
                
        # Fallback to local memory cache
        if settings.dedup_use_local_fallback:
            success = self.local_cache.check_and_set(key)
            return not success
            
        return False
