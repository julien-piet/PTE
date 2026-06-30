#!/usr/bin/env python3
"""
Initialize the PTE test environment.

Starts:
  - SSH port forwarding to the remote worker machine
  - Shopping Extra API server on port 7790
  - Reddit Extra API server on port 7791
  - GitLab Extra API server on port 7792

Then health-checks all configured servers and waits.
Ctrl-C shuts everything down cleanly.

Usage:
    python3 initialize.py                              # reads REMOTE_HOST from config/.env
    python3 initialize.py username@red5k.cs.berkeley.edu   # override REMOTE_HOST

    # Skip shopping extra (e.g. GitLab-only run):
    python3 initialize.py --no-shopping-extra
"""

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent
PORT_FORWARD_SINGLE = PROJECT_ROOT / "eval" / "docker" / "port_forwarding" / "port_forwarding_single.sh"
PORT_FORWARD_MULTI  = PROJECT_ROOT / "eval" / "docker" / "port_forwarding" / "port_forwarding_new.sh"
SHOPPING_EXTRA_SCRIPT = PROJECT_ROOT / "api" / "servers" / "shopping_extra.py"
REDDIT_EXTRA_SCRIPT   = PROJECT_ROOT / "api" / "servers" / "reddit.py"
GITLAB_EXTRA_SCRIPT   = PROJECT_ROOT / "api" / "servers" / "gitlab_extra.py"

load_dotenv(PROJECT_ROOT / "config" / ".env")

_procs: list = []


# ── Shutdown ─────────────────────────────────────────────────────────────────

def _shutdown(signum=None, frame=None):
    print("\n\nShutting down...")
    for proc in _procs:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    print("Done.")
    sys.exit(0)


# ── Health check ─────────────────────────────────────────────────────────────

def _wait_for_http(url: str, label: str, timeout: int = 20) -> bool:
    import urllib.request
    import urllib.error

    print(f"  {label:20s} {url} ", end="", flush=True)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(url, timeout=3)
            print("✓")
            return True
        except urllib.error.HTTPError as e:
            if e.code < 500:  # 4xx is fine — server is up
                print("✓")
                return True
        except Exception:
            pass
        print(".", end="", flush=True)
        time.sleep(1)
    print("✗ (timed out)")
    return False


# ── Service launchers ─────────────────────────────────────────────────────────

def _start_tunnel(script: Path, server: str, label: str) -> None:
    if not script.exists():
        print(f"✗ Script not found: {script}", file=sys.stderr)
        sys.exit(1)
    print(f"  Starting {label} → {server}")
    proc = subprocess.Popen(
        ["bash", str(script), server],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    _procs.append(proc)
    time.sleep(3)  # give SSH time to establish
    if proc.poll() is not None:
        err = proc.stderr.read().decode().strip()
        print(f"✗ {label} failed: {err}", file=sys.stderr)
        sys.exit(1)
    print(f"  ✓ {label} established")


def start_port_forwarding(server: str) -> None:
    print(f"Starting SSH port forwarding → {server}")
    _start_tunnel(PORT_FORWARD_SINGLE, server, "single-instance tunnel")
    _start_tunnel(PORT_FORWARD_MULTI,  server, "multi-docker tunnel")
    print()


def start_shopping_extra() -> None:
    if not SHOPPING_EXTRA_SCRIPT.exists():
        print(f"✗ Shopping extra script not found: {SHOPPING_EXTRA_SCRIPT}", file=sys.stderr)
        sys.exit(1)
    print("Starting Shopping Extra API on port 7790...")
    proc = subprocess.Popen(
        [sys.executable, str(SHOPPING_EXTRA_SCRIPT)],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _procs.append(proc)
    time.sleep(1)
    if proc.poll() is not None:
        print("✗ Shopping Extra API failed to start", file=sys.stderr)
        sys.exit(1)


def start_reddit_extra() -> None:
    if not REDDIT_EXTRA_SCRIPT.exists():
        print(f"✗ Reddit extra script not found: {REDDIT_EXTRA_SCRIPT}", file=sys.stderr)
        sys.exit(1)
    print("Starting Reddit Extra API on port 7791...")
    proc = subprocess.Popen(
        [sys.executable, str(REDDIT_EXTRA_SCRIPT)],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _procs.append(proc)
    time.sleep(1)
    if proc.poll() is not None:
        print("✗ Reddit Extra API failed to start", file=sys.stderr)
        sys.exit(1)


def start_gitlab_extra() -> None:
    if not GITLAB_EXTRA_SCRIPT.exists():
        print(f"✗ GitLab extra script not found: {GITLAB_EXTRA_SCRIPT}", file=sys.stderr)
        sys.exit(1)
    print("Starting GitLab Extra API on port 7792...")
    proc = subprocess.Popen(
        [sys.executable, str(GITLAB_EXTRA_SCRIPT)],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _procs.append(proc)
    time.sleep(1)
    if proc.poll() is not None:
        print("✗ GitLab Extra API failed to start", file=sys.stderr)
        sys.exit(1)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Initialize PTE test environment")
    parser.add_argument(
        "server",
        metavar="USER@HOST",
        nargs="?",
        default=None,
        help="Remote SSH server for port forwarding. Defaults to REMOTE_HOST in config/.env.",
    )
    parser.add_argument(
        "--no-shopping-extra",
        action="store_true",
        default=False,
        help="Skip the Shopping Extra API server (e.g. for GitLab-only runs).",
    )
    parser.add_argument(
        "--no-reddit-extra",
        action="store_true",
        default=False,
        help="Skip the Reddit Extra API server (e.g. for non-Reddit runs).",
    )
    parser.add_argument(
        "--no-gitlab-extra",
        action="store_true",
        default=False,
        help="Skip the GitLab Extra API server (e.g. for non-GitLab runs).",
    )
    args = parser.parse_args()

    server = args.server or os.environ.get("REMOTE_HOST", "")
    if not server:
        parser.error("No server specified — pass USER@HOST or set REMOTE_HOST in config/.env")
    args.server = server

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    print("=" * 50)
    print("  PTE Environment Initialization")
    print("=" * 50 + "\n")

    # 1. Port forwarding
    start_port_forwarding(args.server)

    # 2. Shopping Extra API
    if not args.no_shopping_extra:
        start_shopping_extra()

    # 3. Reddit Extra API
    if not args.no_reddit_extra:
        start_reddit_extra()

    # 4. GitLab Extra API
    if not args.no_gitlab_extra:
        start_gitlab_extra()

    # 5. Health checks
    sys.path.insert(0, str(PROJECT_ROOT))
    from config.servers import SERVER_URLS

    print("\nChecking servers...")
    checks = [
        (SERVER_URLS["gitlab"] + "/users/sign_in", "GitLab"),
        (SERVER_URLS["shopping"],                  "Shopping"),
        (SERVER_URLS["reddit"],                    "Reddit"),
    ]
    if not args.no_shopping_extra:
        checks.append(("http://127.0.0.1:7790/docs", "Shopping Extra"))
    if not args.no_reddit_extra:
        checks.append(("http://127.0.0.1:7791/docs", "Reddit Extra"))
    if not args.no_gitlab_extra:
        checks.append(("http://127.0.0.1:7792/docs", "GitLab Extra"))

    all_ok = all(_wait_for_http(url, label) for url, label in checks)

    print()
    if all_ok:
        print("All services ready. Press Ctrl-C to stop.\n")
    else:
        print("⚠ Some services did not respond — tests may fail.\n")

    # 6. Stay alive, watch for unexpected crashes
    while True:
        time.sleep(2)
        for proc in _procs:
            if proc.poll() is not None:
                print(f"\n⚠ Background process (PID {proc.pid}) exited unexpectedly.", file=sys.stderr)
                _procs.remove(proc)


if __name__ == "__main__":
    main()
