import json
import subprocess
#parallelizing
SERVER = "annabella@red5k.cs.berkeley.edu"
ORCH = "/scr2/webagent/webarena_orchestrator/orchestrator.py"

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


def release_worker(worker_id: int):
    subprocess.run(
        ["ssh", SERVER, f"python3 {ORCH} release --worker-id {worker_id}"],
        check=False
    )