"""
Event-driven routing with Dead Letter Queue support.

This module provides:
- EventRouter: Routes events between pipeline stages
- Dead Letter Queue: Handles failed tasks for manual intervention
- Exponential backoff: Smart retry strategy
- Escalation: Alerts PM Agent for blocked tasks
"""

import asyncio
import logging
from typing import Dict, List, Callable, Optional
from datetime import datetime
from utils.enhanced_components import Event, EventType

logger = logging.getLogger(__name__)


class EventRouter:
    """
    Routes events between pipeline stages with DLQ support.
    
    Features:
    - Event handler registration
    - Automatic retry with exponential backoff
    - Dead Letter Queue for failed tasks
    - Escalation to PM Agent after max retries
    """
    
    MAX_RETRIES = 3
    DLQ_THRESHOLD = 3  # After 3 failures, send to DLQ
    BASE_BACKOFF_SECONDS = 2  # Base for exponential backoff (2^retry_count)
    
    def __init__(self):
        """Initialize event router."""
        self.dead_letter_queue: List[Event] = []
        self.event_handlers: Dict[EventType, List[Callable]] = {}
        self.retry_counts: Dict[str, int] = {}
        
        # Statistics
        self.events_routed = 0
        self.events_failed = 0
        self.dlq_count = 0
        
        logger.info("📮 EventRouter: Initialized")
    
    def register_handler(
        self,
        event_type: EventType,
        handler: Callable
    ):
        """
        Register an event handler.
        
        Args:
            event_type: Type of event to handle
            handler: Async function(event: Event) -> None
        """
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        
        self.event_handlers[event_type].append(handler)
        
        logger.info(
            f"📝 Registered handler '{handler.__name__}' "
            f"for {event_type.value}"
        )
    
    def unregister_handler(
        self,
        event_type: EventType,
        handler: Callable
    ) -> bool:
        """
        Unregister an event handler.
        
        Args:
            event_type: Type of event
            handler: Handler to remove
            
        Returns:
            True if handler was removed, False if not found
        """
        if event_type in self.event_handlers:
            try:
                self.event_handlers[event_type].remove(handler)
                logger.info(
                    f"🗑️ Unregistered handler '{handler.__name__}' "
                    f"for {event_type.value}"
                )
                return True
            except ValueError:
                pass
        return False
    
    async def route_event(self, event: Event):
        """
        Route an event to appropriate handlers.
        
        Implements retry logic with exponential backoff and DLQ escalation.
        
        Args:
            event: Event to route
        """
        try:
            self.events_routed += 1
            
            # Check retry count
            if event.retry_count >= self.MAX_RETRIES:
                logger.warning(
                    f"⚠️ Task {event.task_id} exceeded max retries "
                    f"({self.MAX_RETRIES}), sending to DLQ"
                )
                await self._send_to_dlq(event)
                return
            
            # Get handlers for this event type
            handlers = self.event_handlers.get(event.event_type, [])
            
            if not handlers:
                logger.warning(
                    f"⚠️ No handlers registered for {event.event_type.value}"
                )
                return
            
            # Route to all registered handlers
            for handler in handlers:
                try:
                    logger.debug(
                        f"📮 Routing {event.event_type.value} "
                        f"to {handler.__name__} "
                        f"(task: {event.task_id})"
                    )
                    
                    await handler(event)
                    
                except Exception as e:
                    self.events_failed += 1
                    
                    logger.error(
                        f"❌ Handler '{handler.__name__}' failed "
                        f"for {event.event_type.value}: {e}",
                        exc_info=True
                    )
                    
                    # Increment retry count
                    event.retry_count += 1
                    self.retry_counts[event.task_id] = event.retry_count
                    
                    # Check if should go to DLQ
                    if event.retry_count >= self.DLQ_THRESHOLD:
                        await self._send_to_dlq(event)
                    else:
                        # Retry with exponential backoff
                        backoff = self.BASE_BACKOFF_SECONDS ** event.retry_count
                        logger.info(
                            f"🔄 Retrying task {event.task_id} "
                            f"in {backoff}s (attempt {event.retry_count + 1})"
                        )
                        await asyncio.sleep(backoff)
                        await self.route_event(event)
                    
                    # Don't continue to other handlers if one fails
                    break
                    
        except Exception as e:
            logger.error(
                f"❌ Critical error routing event: {e}",
                exc_info=True
            )
            await self._send_to_dlq(event)
    
    async def _send_to_dlq(self, event: Event):
        """
        Send event to Dead Letter Queue for manual intervention.
        
        Args:
            event: Failed event
        """
        self.dead_letter_queue.append(event)
        self.dlq_count += 1
        
        logger.error(
            f"💀 Sent to DLQ: {event.task_id} "
            f"(type: {event.event_type.value}, "
            f"retries: {event.retry_count}, "
            f"dlq_size: {len(self.dead_letter_queue)})"
        )
        
        # Create escalation event for PM Agent
        escalation_event = Event(
            event_type=EventType.ESCALATE_TO_PM,
            task_id=event.task_id,
            payload={
                'original_event_type': event.event_type.value,
                'original_payload': event.payload,
                'retry_count': event.retry_count,
                'reason': f"Failed after {event.retry_count} retries",
                'timestamp': event.timestamp.isoformat()
            },
            timestamp=datetime.now()
        )
        
        # Trigger escalation handlers (without retry to avoid infinite loop)
        escalation_handlers = self.event_handlers.get(
            EventType.ESCALATE_TO_PM,
            []
        )
        
        for handler in escalation_handlers:
            try:
                await handler(escalation_event)
            except Exception as e:
                logger.error(
                    f"❌ Escalation handler '{handler.__name__}' failed: {e}",
                    exc_info=True
                )
    
    def get_dlq_items(self, limit: Optional[int] = None) -> List[Event]:
        """
        Get items from Dead Letter Queue.
        
        Args:
            limit: Maximum number of items to return (None = all)
            
        Returns:
            List of events in DLQ
        """
        if limit:
            return self.dead_letter_queue[-limit:]
        return self.dead_letter_queue.copy()
    
    def retry_dlq_item(self, task_id: str) -> bool:
        """
        Retry a specific DLQ item.
        
        Args:
            task_id: Task ID to retry
            
        Returns:
            True if item was found and requeued, False otherwise
        """
        for i, event in enumerate(self.dead_letter_queue):
            if event.task_id == task_id:
                # Remove from DLQ
                event = self.dead_letter_queue.pop(i)
                
                # Reset retry count
                event.retry_count = 0
                
                # Re-route
                asyncio.create_task(self.route_event(event))
                
                logger.info(f"🔄 Retrying DLQ item: {task_id}")
                return True
        
        logger.warning(f"⚠️ DLQ item not found: {task_id}")
        return False
    
    def clear_dlq(self):
        """Clear all items from Dead Letter Queue."""
        count = len(self.dead_letter_queue)
        self.dead_letter_queue.clear()
        logger.info(f"🗑️ Cleared DLQ ({count} items removed)")
    
    def get_stats(self) -> Dict[str, any]:
        """
        Get router statistics.
        
        Returns:
            Dictionary with routing metrics
        """
        return {
            'events_routed': self.events_routed,
            'events_failed': self.events_failed,
            'dlq_size': len(self.dead_letter_queue),
            'total_dlq_count': self.dlq_count,
            'retry_counts': dict(self.retry_counts),
            'registered_handlers': {
                event_type.value: len(handlers)
                for event_type, handlers in self.event_handlers.items()
            },
            'failure_rate': (
                round(self.events_failed / self.events_routed * 100, 2)
                if self.events_routed > 0
                else 0.0
            )
        }
    
    def get_handler_count(self, event_type: EventType) -> int:
        """
        Get number of handlers registered for an event type.
        
        Args:
            event_type: Event type to check
            
        Returns:
            Number of registered handlers
        """
        return len(self.event_handlers.get(event_type, []))
    
    def list_event_types(self) -> List[str]:
        """
        List all event types with registered handlers.
        
        Returns:
            List of event type names
        """
        return [et.value for et in self.event_handlers.keys()]
    
    def reset_stats(self):
        """Reset router statistics."""
        self.events_routed = 0
        self.events_failed = 0
        self.dlq_count = len(self.dead_letter_queue)  # Keep current DLQ count
        self.retry_counts.clear()
        logger.info("📊 Router statistics reset")
    
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"EventRouter("
            f"handlers={len(self.event_handlers)}, "
            f"routed={self.events_routed}, "
            f"failed={self.events_failed}, "
            f"dlq={len(self.dead_letter_queue)})"
        )
