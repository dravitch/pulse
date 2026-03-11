import asyncio
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Set

logger = logging.getLogger(__name__)
ws_router = APIRouter()

# Active WebSocket connections
_connections: Set[WebSocket] = set()


async def broadcast(event: str, data: dict) -> None:
    """Broadcast a message to all connected clients."""
    if not _connections:
        return
    message = json.dumps({"event": event, "data": data})
    dead = set()
    for ws in _connections:
        try:
            await ws.send_text(message)
        except Exception:
            dead.add(ws)
    _connections.difference_update(dead)


@ws_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    _connections.add(websocket)
    logger.info(f"WebSocket connected. Total: {len(_connections)}")

    try:
        # Send initial connection confirmation
        await websocket.send_text(json.dumps({
            "event": "connected",
            "data": {"message": "PULSE WebSocket ready"}
        }))

        # Keep alive with ping/pong
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_text(json.dumps({"event": "pong"}))
            except asyncio.TimeoutError:
                # Send keepalive
                await websocket.send_text(json.dumps({"event": "ping"}))

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        _connections.discard(websocket)
