# Running Multiple Docker Instances

## Prerequisites: VS Code Port Configuration

To avoid conflicts with the port forwarding script, add one of the following to your `settings.local.json`:

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
./port_forwarding.sh annabella@red5k.cs.berkeley.edu <#ofworkers>
```
