from abc import ABC, abstractmethod
from typing import Callable, Awaitable, Any

class IngestionAdapter(ABC):
    """
    Abstract base class for all ingestion adapters.
    Each adapter must implement start and stop methods.
    """

    def __init__(self, publish_callback: Callable[[dict], Awaitable[Any]]):
        """
        Initializes the adapter with a callback to publish events.
        
        :param publish_callback: An async function that takes a dictionary 
                                 (the raw notification) and publishes it.
        """
        self.publish_callback = publish_callback

    @abstractmethod
    async def start(self) -> None:
        """
        Start the ingestion adapter. This method should run indefinitely 
        or return when the adapter completes. If it's a long-running process, 
        it should be non-blocking (e.g., spawn its own background tasks) or 
        designed to run in an event loop concurrently.
        """
        pass

    @abstractmethod
    async def stop(self) -> None:
        """
        Stop the ingestion adapter and clean up resources.
        """
        pass
