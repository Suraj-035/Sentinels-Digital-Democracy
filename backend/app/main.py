import asyncio
import threading

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .pipeline_runner import execute_query_job
from .run_manager import run_manager

app = FastAPI(title="Insight Pulse API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=200)
    maxVideos: int = Field(default=2, ge=1, le=5)
    newsLimit: int = Field(default=8, ge=1, le=20)


@app.get("/api/health")
def health():
    return {"ok": True, "app": "insight-pulse-api"}


@app.post("/api/search")
def start_search(payload: SearchRequest):
    query = payload.query.strip()
    run_id, state = run_manager.create_job(query, payload.maxVideos, payload.newsLimit)

    worker = threading.Thread(
        target=execute_query_job,
        args=(run_id, state, run_manager),
        daemon=True,
    )
    worker.start()

    return {"runId": run_id, "state": run_manager.get_state(run_id)}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    state = run_manager.get_state(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return state


@app.websocket("/ws/{run_id}")
async def run_updates(websocket: WebSocket, run_id: str):
    await websocket.accept()

    state = run_manager.get_state(run_id)
    if state is None:
        await websocket.close(code=4404)
        return

    queue = asyncio.Queue()
    subscribed = run_manager.subscribe(run_id, queue, asyncio.get_running_loop())
    if not subscribed:
        await websocket.close(code=4404)
        return

    try:
        await websocket.send_json({"type": "snapshot", "state": state})
        while True:
            event = await queue.get()
            await websocket.send_json(event)
    except WebSocketDisconnect:
        run_manager.unsubscribe(run_id, queue)
