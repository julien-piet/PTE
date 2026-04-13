import asyncio
import json
import subprocess
import time
from contextlib import asynccontextmanager
from typing import Optional

import requests

# parallelizing
SERVER = "annabella@red5k.cs.berkeley.edu"
ORCH = "/scr2/webagent/webarena_orchestrator/orchestrator.py"


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


def release_worker(worker_id: int, read_only: bool = False):
    cmd = f"python3 {ORCH} release --worker-id {worker_id}"
    if read_only:
        cmd += " --read-only"
    subprocess.run(["ssh", SERVER, cmd], check=False)


def wait_for_gitlab(gitlab_url: str, timeout: int = 120, interval: int = 5) -> None:
    """Poll GitLab sign-in page until it returns HTTP 200 or timeout is reached."""
    url = f"{gitlab_url}/users/sign_in"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(interval)
    raise RuntimeError(f"GitLab at {gitlab_url} did not become ready within {timeout}s")


async def acquire_worker_with_retry(
    task_id: str,
    max_attempts: int = 10,
    wait: int = 15,
    acquire_lock: Optional[asyncio.Lock] = None,
) -> dict:
    """
    Acquire a worker for the given task, retrying with a fixed delay on failure.

    Args:
        task_id:      Task identifier (used for logging and orchestrator tracking).
        max_attempts: Maximum number of acquire attempts before raising (default: 10).
        wait:         Seconds to wait between retry attempts (default: 15).
        acquire_lock: Optional asyncio.Lock to serialize each acquire call. Useful
                      when multiple coroutines run concurrently and the orchestrator
                      cannot handle simultaneous acquire requests.

    Returns:
        Worker dict from the orchestrator (contains at least ``worker_id`` and ``gitlab_url``).

    Raises:
        RuntimeError: if no worker could be acquired after all attempts.
    """
    for attempt in range(max_attempts):
        try:
            if acquire_lock is not None:
                async with acquire_lock:
                    return await asyncio.to_thread(acquire_worker, str(task_id))
            return await asyncio.to_thread(acquire_worker, str(task_id))
        except Exception as e:
            print(f"  Task {task_id} acquire failed (attempt {attempt + 1}/{max_attempts}, retry in {wait}s): {e}")
            await asyncio.sleep(wait)
    raise RuntimeError(f"Could not acquire a worker for task {task_id} after {max_attempts} attempts")


@asynccontextmanager
async def worker_session(
    task_id: str,
    max_attempts: int = 10,
    wait: int = 15,
    acquire_lock: Optional[asyncio.Lock] = None,
    read_only: bool = False,
):
    """
    Async context manager that handles the full worker lifecycle:
      acquire → wait for GitLab → obtain GLPAT → yield → release.

    Usage::

        async with worker_session(task_id) as w:
            # w["worker_id"]  — int
            # w["gitlab_url"] — str, e.g. "http://worker1:8023"
            # w["glpat"]      — str, personal access token for this instance

        # With a lock to serialize concurrent acquires:
        lock = asyncio.Lock()
        async with worker_session(task_id, acquire_lock=lock) as w:
            ...

    Args:
        task_id:      Task identifier passed to the orchestrator.
        max_attempts: Passed to acquire_worker_with_retry.
        wait:         Seconds between retry attempts.
        acquire_lock: Optional asyncio.Lock passed to acquire_worker_with_retry.
        read_only:    If True, passes --read-only to the orchestrator on release. #prevents restart of docker if no write into server
    """
    # Import here to avoid a circular import at module load time.
    from eval.docker.gitlab_init import get_glpat

    worker = await acquire_worker_with_retry(
        task_id, max_attempts=max_attempts, wait=wait, acquire_lock=acquire_lock
    )
    worker_id = worker["worker_id"]
    gitlab_url = worker["gitlab_url"]

    try:
        print(f"  Acquired worker {worker_id}: {gitlab_url}")

        print(f"  Waiting for GitLab on worker {worker_id} to be ready...")
        await asyncio.to_thread(wait_for_gitlab, gitlab_url)
        print(f"  GitLab on worker {worker_id} is ready")

        glpat = await asyncio.to_thread(get_glpat, gitlab_url, f"agent-task-{task_id}")
        print(f"  GLPAT obtained for worker {worker_id}")

        yield {**worker, "glpat": glpat}

    finally:
        print(f"  Releasing worker {worker_id}")
        release_worker(worker_id, read_only=read_only)
