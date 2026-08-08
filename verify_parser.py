import json
from src.schemas import CanonicalNotificationEvent
from src.parser.pipeline import NotificationParser

def test_pipeline():
    parser = NotificationParser()
    
    # 1. Test case with amount multipliers
    print("Testing amount multipliers...")
    event1 = CanonicalNotificationEvent(
        source_app_id="test_app",
        raw_payload={},
        title="Token Purchase",
        body="Wallet 0x71C7656EC7ab88b098defB751B7401B5f6d8976F bought 1.5k $SOL"
    )
    result1 = parser.parse(event1)
    
    print("\nResult 1 Entities:")
    for ent in result1.entities:
        print(f" - {ent.entity_type}: {ent.value} (valid: {ent.is_valid})")
        
    print("\nResult 1 Relationships:")
    for rel in result1.relationships:
        print(f" - {rel.subject} -> {rel.action} -> {rel.object_target}")
        
    # 2. Test case with invalid checksum wallet
    print("\n\nTesting invalid checksum...")
    event2 = CanonicalNotificationEvent(
        source_app_id="test_app",
        raw_payload={},
        body="New token from 0x71C7656EC7ab88b098defB751B7401B5f6D8976F" # Invalid checksum character case
    )
    result2 = parser.parse(event2)
    print("\nResult 2 Entities:")
    for ent in result2.entities:
        print(f" - {ent.entity_type}: {ent.value} (valid: {ent.is_valid})")

if __name__ == "__main__":
    test_pipeline()
