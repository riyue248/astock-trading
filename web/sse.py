"""
SSE 实时推送
"""
import asyncio
import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from web.app import sse_queues

logger = logging.getLogger(__name__)
router = APIRouter(tags=["sse"])


async def sse_generator(queue: asyncio.Queue, request: Request):
    try:
        while True:
            if await request.is_disconnected():
                break
            try:
                data = await asyncio.wait_for(queue.get(), timeout=15)
                event_type = data.get("type", "message")
                payload = json.dumps(data, ensure_ascii=False, default=str)
                yield f"event: {event_type}\ndata: {payload}\n\n"
            except asyncio.TimeoutError:
                yield ":ping\n\n"
    except asyncio.CancelledError:
        pass
    finally:
        sse_queues.discard(queue)


@router.get("/sse")
async def sse_stream(request: Request):
    queue = asyncio.Queue(maxsize=1)
    sse_queues.add(queue)
    return StreamingResponse(
        sse_generator(queue, request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
