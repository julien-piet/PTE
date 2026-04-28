# Running Multiple Docker Instances

## Prerequisites: VS Code Port Configuration

To avoid conflicts with the port forwarding script, the server side VS Code should have this enabled (Open User Settings in SSH side): 
This is currently set up, so it shouldn't be a problem...

**Option A — Ignore auto-forward for the port range:**
```json
"remote.portsAttributes": {
    "8024-8030": {
        "onAutoForward": "ignore"
    }
}
```

**Option B — Disable auto-forwarding entirely:**
```json
"remote.autoForwardPorts": false
```

---

## Managing Workers (run from your local terminal)

NEW version:

| Action | Command |
|--------|---------|
| Check status | `ssh username@red5k.cs.berkeley.edu 'python3 /scr2/webagent-verified/webarena_orchestrator/orchestrator.py status'` |
| Stop all workers | `ssh username@red5k.cs.berkeley.edu 'python3 /scr2/webagent-verified/webarena_orchestrator/orchestrator.py down'` |
| Init workers | `ssh username@red5k.cs.berkeley.edu 'python3 /scr2/webagent-verified/webarena_orchestrator/orchestrator.py init --num-workers <#ofworkers>'` |
| Release a worker | `ssh username@red5k.cs.berkeley.edu 'python3 /scr2/webagent-verified/webarena_orchestrator/orchestrator.py release --worker-id <id>'` |

> **Note:** `init` defaults to 3 workers if no number is provided.

---

## Port Forwarding

Run from the `PTE/scripts/docker_parallel` directory:

```bash
./port_forwarding_new.sh annabella@red5k.cs.berkeley.edu
```




Old docker image use these.

| Action | Command |
|--------|---------|
| Check status | `ssh username@red5k.cs.berkeley.edu 'python3 /scr2/webagent/webarena_orchestrator/orchestrator.py status'` |
| Stop all workers | `ssh username@red5k.cs.berkeley.edu 'python3 /scr2/webagent/webarena_orchestrator/orchestrator.py down'` |
| Init workers | `ssh username@red5k.cs.berkeley.edu 'python3 /scr2/webagent/webarena_orchestrator/orchestrator.py init --num-workers <#ofworkers>'` |
| Release a worker | `ssh username@red5k.cs.berkeley.edu 'python3 /scr2/webagent/webarena_orchestrator/orchestrator.py release --worker-id <id>'` |

> **Note:** `init` defaults to 3 workers if no number is provided.

---

## Port Forwarding

Run from the `PTE/scripts/docker_parallel` directory:

```bash
./port_forwarding_old.sh annabella@red5k.cs.berkeley.edu
```
