import json
import subprocess
#parallelizing
SERVER = "annabella@red5k.cs.berkeley.edu"
ORCH = "/scr2/webagent/webarena_orchestrator/orchestrator.py"

def acquire_worker(task_id: str) -> dict:
    out = subprocess.check_output(
        ["ssh", SERVER, f"python3 {ORCH} acquire --task-id {task_id}"],
        text=True
    )
    data = json.loads(out)
    if "error" in data:
        raise RuntimeError("No available workers")
    return data


def release_worker(worker_id: int):
    subprocess.run(
        ["ssh", SERVER, f"python3 {ORCH} release --worker-id {worker_id}"],
        check=False
    )