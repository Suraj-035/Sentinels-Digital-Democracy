import copy
import threading
import uuid
from datetime import datetime, timezone


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class RunManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._jobs = {}

    def create_job(self, query, max_videos, news_limit):
        run_id = uuid.uuid4().hex
        state = {
            "runId": run_id,
            "query": query,
            "status": "queued",
            "startedAt": utc_now(),
            "updatedAt": utc_now(),
            "options": {
                "maxVideos": max_videos,
                "newsLimit": news_limit,
            },
            "progress": {
                "stage": "queued",
                "message": "Waiting to start",
            },
            "news": {
                "completed": False,
                "query": query,
                "summary": {},
                "results": [],
            },
            "youtube": {
                "completed": False,
                "videos": [],
            },
            "errors": [],
        }

        with self._lock:
            self._jobs[run_id] = {
                "state": state,
                "subscribers": [],
            }

        return run_id, copy.deepcopy(state)

    def get_state(self, run_id):
        with self._lock:
            job = self._jobs.get(run_id)
            if not job:
                return None
            return copy.deepcopy(job["state"])

    def subscribe(self, run_id, queue, loop):
        with self._lock:
            job = self._jobs.get(run_id)
            if not job:
                return False
            job["subscribers"].append((queue, loop))
            return True

    def unsubscribe(self, run_id, queue):
        with self._lock:
            job = self._jobs.get(run_id)
            if not job:
                return
            job["subscribers"] = [
                (subscriber_queue, loop)
                for subscriber_queue, loop in job["subscribers"]
                if subscriber_queue is not queue
            ]

    def publish(self, run_id, event_type, state):
        with self._lock:
            job = self._jobs.get(run_id)
            if not job:
                return

            state["updatedAt"] = utc_now()
            job["state"] = copy.deepcopy(state)
            subscribers = list(job["subscribers"])

        event = {
            "type": event_type,
            "state": copy.deepcopy(state),
            "timestamp": utc_now(),
        }

        for queue, loop in subscribers:
            loop.call_soon_threadsafe(queue.put_nowait, event)


run_manager = RunManager()
