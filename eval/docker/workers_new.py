# eval/docker/workers_new.py
#
# Worker session for the new multi-server orchestrator.
# Each worker exposes all four services (shopping, shopping_admin, reddit, gitlab)
# on separate ports. Port forwarding maps them to localhost:{port}.
#
# Orchestrator: /scr2/webagent-verified/webarena_orchestrator/orchestrator.py

import asyncio
import json
import subprocess
import time
from contextlib import asynccontextmanager
from typing import Optional

import requests

SERVER = "annabella@red5k.cs.berkeley.edu"
ORCH = "/scr2/webagent-verified/webarena_orchestrator/orchestrator.py"

# Maps server name → the URL field returned by the orchestrator's acquire command.
_URL_FIELD = {
    "gitlab":         "gitlab_url",
    "shopping":       "shopping_url",
    "shopping_admin": "shopping_admin_url",
    "reddit":         "reddit_url",
}


def num_workers() -> int:
    result = subprocess.run(
        ["ssh", SERVER, f"python3 {ORCH} num_workers"],
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"num_workers exited {result.returncode}: "
            f"stdout={result.stdout.strip()!r} stderr={result.stderr.strip()!r}"
        )
    return int(result.stdout.strip())


def acquire_worker(task_id: str) -> dict:
    result = subprocess.run(
        ["ssh", SERVER, f"python3 {ORCH} acquire --task-id {task_id}"],
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"acquire_worker exited {result.returncode}: "
            f"stdout={result.stdout.strip()!r} stderr={result.stderr.strip()!r}"
        )
    data = json.loads(result.stdout)
    if "error" in data:
        raise RuntimeError(f"No available workers: {data['error']}")
    return data


def release_worker(worker_id: int) -> None:
    cmd = f"python3 {ORCH} release --worker-id {worker_id}"
    subprocess.run(["ssh", SERVER, cmd], check=False)


def wait_for_server(url: str, timeout: int = 120, interval: int = 5) -> None:
    """Poll server URL until HTTP 200 or timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(interval)
    raise RuntimeError(f"Server at {url} did not become ready within {timeout}s")


def _health_url(server: str, base_url: str) -> str:
    if server == "gitlab":
        return f"{base_url}/users/sign_in"
    return base_url


async def acquire_worker_with_retry(
    task_id: str,
    server: str,
    max_attempts: int = 10,
    wait: int = 15,
    acquire_lock: Optional[asyncio.Lock] = None,
) -> dict:
    """Acquire a worker that has `server` enabled, retrying on failure or disabled service."""
    url_field = _URL_FIELD[server]
    for attempt in range(max_attempts):
        try:
            if acquire_lock is not None:
                async with acquire_lock:
                    worker = await asyncio.to_thread(acquire_worker, str(task_id))
            else:
                worker = await asyncio.to_thread(acquire_worker, str(task_id))

            if not worker.get(url_field):
                release_worker(worker["worker_id"])
                raise RuntimeError(
                    f"Worker {worker['worker_id']} has {server!r} disabled (url is null). "
                    f"Start the service or choose a different server."
                )

            return worker

        except Exception as e:
            print(f"  Task {task_id} acquire failed (attempt {attempt + 1}/{max_attempts}, retry in {wait}s): {e}")
            await asyncio.sleep(wait)

    raise RuntimeError(
        f"Could not acquire a worker with {server!r} enabled for task {task_id} "
        f"after {max_attempts} attempts"
    )


@asynccontextmanager
async def worker_session(
    task_id: str,
    server: str,
    max_attempts: int = 10,
    wait: int = 15,
    acquire_lock: Optional[asyncio.Lock] = None,
):
    """
    Async context manager for the new multi-server worker pool.

    Acquires a worker, waits for the requested service to be healthy,
    obtains a GLPAT for gitlab (other servers use static tokens from .server_env),
    yields the session dict, then releases the worker.

    Usage::

        async with worker_session(task_id, server="gitlab", acquire_lock=lock) as w:
            # w["worker_id"]  — int
            # w["gitlab_url"] — str, e.g. "http://localhost:20016"
            # w["glpat"]      — str for gitlab, None for other servers

    """
    if server not in _URL_FIELD:
        raise ValueError(f"Unknown server {server!r}. Known: {list(_URL_FIELD)}")

    worker = await acquire_worker_with_retry(
        task_id, server=server, max_attempts=max_attempts, wait=wait, acquire_lock=acquire_lock
    )
    worker_id = worker["worker_id"]
    # Orchestrator returns 127.0.0.1; replace with localhost since port forwarding
    # tunnels the remote ports to the same port numbers on this machine.
    server_url = worker[_URL_FIELD[server]].replace("127.0.0.1", "localhost")

    try:
        print(f"  Acquired worker {worker_id} → task {task_id} ({server} @ {server_url})")

        health = _health_url(server, server_url)
        print(f"  Waiting for {server} on worker {worker_id} to be ready...")
        await asyncio.to_thread(wait_for_server, health)
        print(f"  {server} on worker {worker_id} is ready")

        glpat = None
        if server == "gitlab":
            from eval.docker.gitlab_init import get_glpat
            glpat = await asyncio.to_thread(get_glpat, server_url, f"agent-task-{task_id}")
            print(f"  GLPAT obtained for worker {worker_id}")

        yield {"worker_id": worker_id, "gitlab_url": server_url, "glpat": glpat}

    finally:
        print(f"  Releasing worker {worker_id}")
        release_worker(worker_id)
