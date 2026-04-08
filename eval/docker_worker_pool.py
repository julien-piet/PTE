"""
docker_worker_pool.py

Manages multiple GitLab Docker containers running on red5k via the WebArena
orchestrator. Each worker gets its own fresh GitLab container on a dedicated
port; port_forwarding.sh tunnels those ports to localhost.

Port layout (same-port forwarding — local == remote):
  Worker N → localhost:{8023+N}  (e.g. worker 1 → localhost:8024)

Before running a task with require_reset=True, call reset_worker(worker_id).
This SSHes to red5k and runs:
  orchestrator.py release --worker-id N
then polls localhost:{port}/api/v4/version until the container responds.

Usage:
    async with DockerWorkerPool(3, "sylvie@red5k.cs.berkeley.edu") as pool:
        worker = await pool.acquire()
        try:
            if task.get("require_reset"):
                await pool.reset_worker(worker.worker_id)
            result = await runner_for(worker).run_agent_on_task(task)
        finally:
            pool.release(worker.worker_id)

Temp api dirs:
    Each worker gets a private copy of the api/ directory with the GitLab
    schema host patched to 127.0.0.1:{worker_port}.  These are cleaned up
    automatically when the pool is used as a context manager.
"""

import asyncio
import json
import shutil
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional


# ---------------------------------------------------------------------------
# Per-worker PAT creation (Playwright, runs in thread executor)
# ---------------------------------------------------------------------------

def _create_pat_for_port(port: int) -> str:
    """
    Log in as byteblaze on the GitLab container at localhost:{port} and
    create (or retrieve) a PAT named 'benchmark-runner'.

    Runs synchronously — call via asyncio.run_in_executor for async use.
    """
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    gitlab_url = f"http://127.0.0.1:{port}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Log in
        page.goto(f"{gitlab_url}/users/sign_in", wait_until="networkidle")
        page.fill("#user_login", "byteblaze")
        page.fill("#user_password", "hello1234")
        page.locator('button[type="submit"]').click()
        page.wait_for_load_state("networkidle")

        # Navigate to PAT page
        page.goto(
            f"{gitlab_url}/-/profile/personal_access_tokens",
            wait_until="networkidle",
        )

        # Fill token name
        page.locator("#personal_access_token_name").fill("benchmark-runner")

        # Select 'api' scope
        label = page.locator("label[for='personal_access_token_scopes_api']")
        if label.count() > 0:
            label.click()
        else:
            page.locator("#personal_access_token_scopes_api").click(force=True)

        # Submit
        submit = page.locator(
            "button:has-text('Create personal access token'), input[name='commit']"
        ).first
        submit.click()
        page.wait_for_load_state("networkidle")

        # Extract token value
        try:
            page.wait_for_selector(
                "[data-clipboard-text^='glpat-']",
                timeout=5000,
                state="attached",
            )
            clip = page.locator("[data-clipboard-text^='glpat-']").first
            token = clip.get_attribute("data-clipboard-text") or ""
        except PWTimeout:
            # Fallback: older GitLab versions expose token in a plain input
            token_el = page.locator("#created-personal-access-token")
            if token_el.count() > 0:
                token = token_el.get_attribute("value") or token_el.inner_text()
            else:
                raise RuntimeError(
                    f"Could not find PAT token element on worker at port {port}"
                )

        browser.close()

    return token.strip()


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class WorkerResetError(RuntimeError):
    """Raised when the orchestrator release command fails."""


class WorkerHealthTimeout(RuntimeError):
    """Raised when a worker container does not become healthy in time."""


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

@dataclass
class DockerWorker:
    worker_id: int
    api_dir: str            # path to this worker's patched api directory
    env_file: str = ""      # path to this worker's .server_env (set after PAT creation)
    _tmp_dir: Optional[str] = field(default=None, repr=False)

    @property
    def port(self) -> int:
        return 8023 + self.worker_id

    @property
    def gitlab_base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def cleanup(self) -> None:
        if self._tmp_dir:
            shutil.rmtree(self._tmp_dir, ignore_errors=True)
            self._tmp_dir = None


# ---------------------------------------------------------------------------
# Pool
# ---------------------------------------------------------------------------

class DockerWorkerPool:
    """
    Context-managed pool of N Docker workers.

    Parameters
    ----------
    num_workers : int
        Number of worker containers (1–N). Worker IDs are 1-indexed.
    remote_host : str
        SSH target for orchestrator commands, e.g. "sylvie@red5k.cs.berkeley.edu"
    source_api_dir : str
        Path to the canonical api/ directory. Each worker gets a private
        copy with its GitLab schema host patched to 127.0.0.1:{port}.
    health_timeout : int
        Seconds to wait for a container to become healthy after release.
    health_interval : float
        Seconds between health-check polls.
    """

    ORCHESTRATOR = "/scr2/webagent/webarena_orchestrator/orchestrator.py"

    def __init__(
        self,
        num_workers: int,
        remote_host: str,
        source_api_dir: str = "api",
        health_timeout: int = 120,
        health_interval: float = 3.0,
    ) -> None:
        self.num_workers = num_workers
        self.remote_host = remote_host
        self.source_api_dir = source_api_dir
        self.health_timeout = health_timeout
        self.health_interval = health_interval

        self._workers: Dict[int, DockerWorker] = {}
        self._free: asyncio.Queue = asyncio.Queue()

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "DockerWorkerPool":
        self._setup_workers()
        await self._init_worker_tokens()
        return self

    async def __aexit__(self, *_) -> None:
        self.cleanup()

    # ------------------------------------------------------------------
    # Setup / teardown
    # ------------------------------------------------------------------

    def _setup_workers(self) -> None:
        """Create per-worker api dirs and populate the free queue."""
        for wid in range(1, self.num_workers + 1):
            api_dir = self._patch_api_dir(wid)
            worker = DockerWorker(worker_id=wid, api_dir=api_dir, _tmp_dir=api_dir)
            self._workers[wid] = worker
            self._free.put_nowait(wid)

    def _patch_api_dir(self, worker_id: int) -> str:
        """
        Copy the source api/ dir to a temp location and patch the GitLab
        schema host to point at this worker's local port.
        """
        tmp = tempfile.mkdtemp(prefix=f"pte_api_worker{worker_id}_")
        shutil.copytree(self.source_api_dir, tmp, dirs_exist_ok=True)

        schema_path = Path(tmp) / "gitlab_api_schema.json"
        if schema_path.exists():
            with open(schema_path) as f:
                schema = json.load(f)
            schema["host"] = f"127.0.0.1:{8023 + worker_id}"
            with open(schema_path, "w") as f:
                json.dump(schema, f)

        return tmp

    def cleanup(self) -> None:
        """Remove all temp api dirs."""
        for worker in self._workers.values():
            worker.cleanup()

    async def _init_worker_tokens(self) -> None:
        """
        Create a GitLab PAT for each worker by logging in as byteblaze via
        Playwright and submitting the PAT form.  The token is written to a
        per-worker .server_env file inside the worker's api_dir so that each
        AgentRunner can load its own GITLAB_TOKEN.
        """
        loop = asyncio.get_event_loop()
        for wid in range(1, self.num_workers + 1):
            worker = self._workers[wid]
            print(f"   🔑 Creating PAT for worker {wid} (port {worker.port})...")
            try:
                token = await loop.run_in_executor(
                    None, _create_pat_for_port, worker.port
                )
            except Exception as exc:
                raise WorkerResetError(
                    f"Failed to create PAT for worker {wid} (port {worker.port}): {exc}"
                ) from exc

            env_path = Path(worker.api_dir) / ".server_env"
            env_path.write_text(f"GITLAB_TOKEN={token}\n")
            worker.env_file = str(env_path)
            print(f"   ✅ Worker {wid} PAT ready ({token[:12]}...)")

    # ------------------------------------------------------------------
    # Worker acquisition
    # ------------------------------------------------------------------

    async def acquire(self) -> DockerWorker:
        """Block until a worker is free, then return it (marked busy)."""
        worker_id = await self._free.get()
        return self._workers[worker_id]

    def release(self, worker_id: int) -> None:
        """Mark a worker as free so other tasks can use it."""
        self._free.put_nowait(worker_id)

    def get_worker(self, worker_id: int) -> DockerWorker:
        return self._workers[worker_id]

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    async def reset_worker(self, worker_id: int) -> None:
        """
        Release and reinitialize the worker's Docker container.

        Sends `orchestrator.py release --worker-id N` via SSH, then polls
        until the container's GitLab API responds with HTTP 200.
        """
        port = 8023 + worker_id
        print(f"   🔄 Resetting worker {worker_id} (localhost:{port})...")

        cmd = [
            "ssh", "-o", "BatchMode=yes",
            self.remote_host,
            f"python3 {self.ORCHESTRATOR} release --worker-id {worker_id}",
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)

        if proc.returncode != 0:
            raise WorkerResetError(
                f"orchestrator release failed for worker {worker_id} "
                f"(exit {proc.returncode}): {stderr.decode().strip()}"
            )

        print(f"   ⏳ Waiting for worker {worker_id} to become healthy...")
        await self._wait_for_healthy(worker_id)
        print(f"   ✅ Worker {worker_id} ready.")

    async def _wait_for_healthy(self, worker_id: int) -> None:
        """Poll GET /api/v4/version until the container responds 200."""
        port = 8023 + worker_id
        url = f"http://127.0.0.1:{port}/api/v4/version"
        loop = asyncio.get_event_loop()
        deadline = loop.time() + self.health_timeout

        while loop.time() < deadline:
            try:
                resp = await loop.run_in_executor(
                    None,
                    lambda: urllib.request.urlopen(url, timeout=5),
                )
                if resp.status == 200:
                    return
            except Exception:
                pass
            await asyncio.sleep(self.health_interval)

        raise WorkerHealthTimeout(
            f"Worker {worker_id} (localhost:{port}) did not become healthy "
            f"within {self.health_timeout}s"
        )

    # ------------------------------------------------------------------
    # Convenience: orchestrator status
    # ------------------------------------------------------------------

    async def status(self) -> str:
        """Return the raw output of `orchestrator.py status`."""
        cmd = [
            "ssh", "-o", "BatchMode=yes",
            self.remote_host,
            f"python3 {self.ORCHESTRATOR} status",
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
        return stdout.decode()
