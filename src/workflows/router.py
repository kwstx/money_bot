import logging
import asyncio
from typing import List, Type
from ..schemas import CanonicalNotificationEvent
from .base import Workflow
from .discovery import DiscoveryWorkflow
from .security import SecurityWorkflow
from .wallet import WalletWorkflow
from .market import MarketWorkflow
from .social import SocialWorkflow
from .narrative import NarrativeWorkflow
from .risk import RiskWorkflow

logger = logging.getLogger(__name__)

class WorkflowRouter:
    """
    The WorkflowRouter subscribes to the canonical message bus (via consumer)
    and dispatches the incoming events to the appropriate downstream intelligence workflows.
    This fulfills the requirement that a new token enters once and automatically triggers
    all workflows without independent polling.
    """
    def __init__(self):
        self.workflows: List[Workflow] = [
            DiscoveryWorkflow(),
            SecurityWorkflow(),
            WalletWorkflow(),
            MarketWorkflow(),
            SocialWorkflow(),
            NarrativeWorkflow(),
            RiskWorkflow()
        ]

    async def route_event(self, event_payload: dict) -> None:
        """
        Main entrypoint for the Kafka consumer.
        Takes the raw JSON dict from Kafka, parses it into CanonicalNotificationEvent,
        and fires all applicable workflows concurrently.
        """
        try:
            event = CanonicalNotificationEvent(**event_payload)
        except Exception as e:
            logger.error(f"Failed to parse canonical event in router: {e}")
            raise # Let the DurableConsumer handle retries / DLQ

        logger.info(f"Routing Canonical Event {event.event_id} (Category: {event.event_category})")

        # Fan-out to all workflows. Each workflow decides internally if it cares about this event category.
        tasks = []
        for wf in self.workflows:
            tasks.append(asyncio.create_task(self._safe_execute_workflow(wf, event)))
            
        await asyncio.gather(*tasks)

    async def _safe_execute_workflow(self, workflow: Workflow, event: CanonicalNotificationEvent) -> None:
        try:
            # We check if the workflow wants to process it based on its own internal logic.
            await workflow.process(event)
        except Exception as e:
            # We don't fail the entire routing if one downstream workflow fails,
            # but we should log and potentially emit a metric/alert.
            logger.error(f"Workflow {workflow.name} failed to process event {event.event_id}: {e}")

router = WorkflowRouter()
