from fastapi import WebSocket
import asyncio
import logging
from collections import deque

logger = logging.getLogger("websocket_manager")


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.lock = asyncio.Lock()
        self._loop = None
        self._pending_messages = deque(maxlen=100)  # buffer until loop ready
        self._warned_no_loop = False  # avoid log spam
        self._flush_tasks = []  # prevent premature GC of flush tasks

    async def connect(self, websocket: WebSocket):
        # store main loop when first websocket connects
        if not self._loop:
            self._loop = asyncio.get_running_loop()
            # flush any pending messages queued before loop ready
            if self._pending_messages:
                logger.info(f"🌀 Flushing {len(self._pending_messages)} queued broadcasts...")
                tasks = []
                while self._pending_messages:
                    msg = self._pending_messages.popleft()
                    task = asyncio.create_task(self.broadcast(msg))
                    tasks.append(task)
                # store tasks to prevent GC until complete
                self._flush_tasks.extend(tasks)
                # optional cleanup once all flush tasks finish
                asyncio.create_task(self._cleanup_tasks(tasks))

        await websocket.accept()
        async with self.lock:
            self.active_connections.append(websocket)
        logger.info(f"✅ WebSocket connected: {id(websocket)} | Total: {len(self.active_connections)}")

    async def _cleanup_tasks(self, tasks):
        """Remove completed flush tasks after they're done to avoid memory growth."""
        try:
            await asyncio.gather(*tasks)
        finally:
            for t in tasks:
                if t in self._flush_tasks:
                    self._flush_tasks.remove(t)

    async def disconnect(self, websocket: WebSocket):
        async with self.lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
        logger.info(f"❌ WebSocket disconnected: {id(websocket)} | Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Send message to all connected clients safely (async context)."""
        async with self.lock:
            if not self.active_connections:
                return

            to_remove = []
            for connection in self.active_connections:
                try:
                    if connection.application_state.name == "CONNECTED":
                        await connection.send_json(message)
                    else:
                        to_remove.append(connection)
                except Exception as e:
                    logger.warning(f"⚠️ Failed to send to {id(connection)}: {e}")
                    to_remove.append(connection)

            for conn in to_remove:
                if conn in self.active_connections:
                    self.active_connections.remove(conn)
                    logger.info(
                        f"🧹 Removed closed socket: {id(conn)} | Remaining: {len(self.active_connections)}"
                    )

    def safe_broadcast(self, message: dict):
        """
        ✅ Safe to call from background threads.
        If loop isn't ready yet, message is queued instead of spamming logs.
        """
        if not self._loop:
            if not self._warned_no_loop:
                logger.warning("⚠️ WebSocket loop not ready — queueing broadcasts until connected.")
                self._warned_no_loop = True
            self._pending_messages.append(message)
            return

        try:
            asyncio.run_coroutine_threadsafe(self.broadcast(message), self._loop)
        except Exception as e:
            logger.error(f"❌ safe_broadcast failed: {e}")


manager = ConnectionManager()
