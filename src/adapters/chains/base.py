from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from ...discovery.schemas import UnifiedChainEvent, EventType

class ChainAdapter(ABC):
    """
    Abstract Base Class for Chain Adapters.
    Encapsulates chain-specific finality, transaction formats, token standards,
    and DEX structures while producing uniform internal UnifiedChainEvent objects.
    """

    @property
    @abstractmethod
    def chain_id(self) -> str:
        """Return canonical chain name (e.g. 'ethereum', 'solana', 'base')."""
        pass

    @property
    @abstractmethod
    def required_confirmations(self) -> int:
        """Return required block confirmations for chain finality."""
        pass

    @abstractmethod
    def normalize_address(self, address: str) -> str:
        """Normalize address according to chain rules (e.g. checksum EVM, base58 Solana)."""
        pass

    @abstractmethod
    def parse_transaction(self, raw_tx: Dict[str, Any]) -> List[UnifiedChainEvent]:
        """Parse raw chain transaction into unified chain events."""
        pass

    @abstractmethod
    def parse_log_event(self, raw_log: Dict[str, Any]) -> Optional[UnifiedChainEvent]:
        """Parse chain contract event log into unified event."""
        pass
