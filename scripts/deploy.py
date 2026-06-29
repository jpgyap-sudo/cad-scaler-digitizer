#!/usr/bin/env python3
"""
deploy.py — Smart Multi-Source Deployer Agent
==============================================

Designed for repos where multiple coding assistants (Codex, Kilo Code,
Blackbox, SuperRoo, Claude Code, etc.) all push to the same repo concurrently.
Instead of each agent triggering its own deploy race, this agent:

  1. Fetches latest remote state and pulls any new commits (regardless of author)
  2. Identifies ALL commits since last deploy with multi-agent attribution
  3. Detects which Docker services are actually affected by the changed files
  4. Acquires a remote deploy lock to prevent concurrent/overlapping deploys
  5. Selectively rebuilds ONLY changed services (not the whole stack every time)
  6. Runs post-deploy health checks and auto-rolls back on failure
  7. Persists full deploy history locally (.deploy_state.json) + on VPS

Usage:
  python scripts/deploy.py                        # deploy all pending commits
  python scripts/deploy.py --dry-run              # show plan, no changes
  python scripts/deploy.py --force                # skip lock check (emergency)
  python scripts/deploy.py --agent KiloCode       # tag who triggered this
  python scripts/deploy.py --services python-worker frontend
  python scripts/deploy.py --history              # show deploy history
  python scripts/deploy.py --status               # live VPS service status
  python scripts/deploy.py --rollback             # rollback to previous deploy
  python scripts/deploy.py --health               # run health check only
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ─── Config ───────────────────────────────────────────────────────────────────

VPS_HOST = "104.248.225.250"
VPS_USER = "root"
SSH_KEY   = Path.home() / ".ssh" / "id_superroo_vps"
VPS_APP   = "/opt/cad-digitizer"

# Health endpoints checked after every deploy (called on VPS via curl)
HEALTH_ENDPOINTS = [
    ("python-worker", "http://localhost:8001/health"),
    ("node-api",      "http://localhost:4000/health"),
]
HEALTH_SETTLE_S = 15  # seconds to wait before first health check

STATE_FILE = Path(__file__).parent / ".deploy_state.json"
REPO_ROOT  = Path(__file__).parent.parent

# File-path prefix → which docker-compose services to rebuild
SERVICE_MAP: dict[str, list[str]] = {
    "frontend/":                    ["frontend"],
    "backend-python/":              ["python-worker"],
    "backend-python/resources/":    ["python-worker"],
    "resources/":                   ["python-worker"],
    "node-api/":                    ["node-api"],
    "crawler/":                     ["crawler-worker"],
    "mcp/":                         ["mcp-server"],
    "docker-compose.yml":           ["frontend", "node-api", "python-worker", "crawler-worker", "mcp-server"],
    "docker-compose.prod.yml":      ["frontend", "node-api", "python-worker", "crawler-worker", "mcp-server"],
    "Dockerfile.frontend":          ["frontend"],
    "Dockerfile.node-api":          ["node-api"],
    "Dockerfile.python-worker":     ["python-worker"],
    "Dockerfile.crawler-worker":    ["crawler-worker"],
    "Dockerfile.mcp":               ["mcp-server"],
}

ALL_BUILDABLE = ["frontend", "node-api", "python-worker", "crawler-worker", "mcp-server"]
LOCK_PATH     = f"{VPS_APP}/.deploying"
REMOTE_LOG    = f"{VPS_APP}/.deploy_log.json"

# ─── State ────────────────────────────────────────────────────────────────────

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"last_deployed_commit": None, "deployments": []}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")


# ─── Git ──────────────────────────────────────────────────────────────────────

def _run(cmd: str, cwd=None, check=True, capture=True) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, shell=True, cwd=str(cwd or REPO_ROOT),
        capture_output=capture, text=True, check=check,
    )


def git(cmd: str) -> str:
    return _run(f"git {cmd}").stdout.strip()


def current_commit() -> str:
    return git("rev-parse HEAD")


def fetch_remote() -> str:
    _run("git fetch origin master --quiet")
    return git("rev-parse origin/master")


def commits_between(base: str, head: str = "HEAD") -> list[dict]:
    """Commits base..head (base excluded). Returns [] if base is None (first deploy)."""
    if not base:
        raw = git(f"log {head} --pretty=format:%H|%an|%ae|%s|%ai --max-count=10")
    else:
        raw = git(f"log {base}..{head} --pretty=format:%H|%an|%ae|%s|%ai")
    if not raw:
        return []
    results = []
    for line in raw.splitlines():
        parts = line.split("|", 4)
        if len(parts) == 5:
            results.append({
                "hash": parts[0], "author": parts[1],
                "email": parts[2], "message": parts[3], "date": parts[4],
            })
    return results


def changed_files_between(base: str, head: str = "HEAD") -> list[str]:
    if not base:
        return []
    out = git(f"diff --name-only {base}..{head}")
    return [f for f in out.splitlines() if f]


def detect_services(changed_files: list[str]) -> list[str]:
    affected: set[str] = set()
    for f in changed_files:
        matched = False
        for prefix, svcs in SERVICE_MAP.items():
            if f.startswith(prefix) or f == prefix.rstrip("/"):
                affected.update(svcs)
                matched = True
                break
        if not matched:
            # Unknown area — safest to rebuild everything
            return ALL_BUILDABLE[:]
    return sorted(affected) if affected else ALL_BUILDABLE[:]


# ─── SSH ──────────────────────────────────────────────────────────────────────

def _ssh_cmd(remote_cmd: str) -> str:
    key = str(SSH_KEY).replace("\\", "/")
    return f'ssh -i "{key}" -o StrictHostKeyChecking=no -o ConnectTimeout=15 {VPS_USER}@{VPS_HOST} \'{remote_cmd}\''


def ssh(remote_cmd: str, check=True, capture=True) -> subprocess.CompletedProcess:
    return subprocess.run(
        _ssh_cmd(remote_cmd), shell=True,
        capture_output=capture, text=True, check=check,
    )


def ssh_out(remote_cmd: str, default: str = "") -> str:
    try:
        return ssh(remote_cmd).stdout.strip()
    except Exception:
        return default


# ─── Deploy lock ──────────────────────────────────────────────────────────────

def acquire_lock(agent: str, force: bool = False) -> bool:
    existing = ssh_out(f"cat {LOCK_PATH} 2>/dev/null || echo __none__")
    if existing != "__none__" and existing.strip():
        if not force:
            return False
        print(f"  WARNING: overriding existing lock: {existing[:120]}")
    payload = json.dumps({"agent": agent, "pid": os.getpid(),
                          "started": datetime.now(timezone.utc).isoformat()})
    ssh(f"echo '{payload}' > {LOCK_PATH}", check=False)
    return True


def release_lock():
    ssh(f"rm -f {LOCK_PATH}", check=False, capture=True)


# ─── Health check ─────────────────────────────────────────────────────────────

def run_health_check() -> tuple[bool, list[str]]:
    lines = []
    all_ok = True
    for name, url in HEALTH_ENDPOINTS:
        out = ssh_out(f"curl -sf --max-time 10 '{url}' 2>/dev/null && echo OK || echo FAIL")
        ok = out.strip().endswith("OK")
        lines.append(f"  {'[OK]  ' if ok else '[FAIL]'} {name:<20} {url}")
        if not ok:
            all_ok = False

    # docker compose ps — flag unhealthy containers
    ps_raw = ssh_out(
        f"cd {VPS_APP} && docker compose ps --format '{{{{.Service}}}}|{{{{.Status}}}}|{{{{.Health}}}}' 2>/dev/null"
    )
    unhealthy = []
    for row in ps_raw.splitlines():
        parts = row.split("|")
        if len(parts) >= 3:
            svc, status, health = parts[0], parts[1], parts[2]
            if health.lower() == "unhealthy" or ("up" not in status.lower() and "running" not in status.lower()):
                unhealthy.append(f"{svc}({health or status})")
    if unhealthy:
        lines.append(f"  [WARN] Unhealthy containers: {', '.join(unhealthy)}")
        all_ok = False

    return all_ok, lines


# ─── Remote deploy log ────────────────────────────────────────────────────────

def append_remote_log(entry: dict):
    raw = ssh_out(f"cat {REMOTE_LOG} 2>/dev/null || echo '[]'")
    try:
        log = json.loads(raw)
    except Exception:
        log = []
    log.append(entry)
    log = log[-50:]  # keep last 50
    payload = json.dumps(log, default=str).replace("'", r"'\''")
    ssh(f"printf '%s' '{payload}' > {REMOTE_LOG}", check=False)


# ─── Sub-commands ─────────────────────────────────────────────────────────────

def cmd_history(state: dict):
    deployments = state.get("deployments", [])
    if not deployments:
        print("  No local deploy history yet.")
    else:
        print(f"\n  Local deploy history ({len(deployments)} records):\n")
        for d in reversed(deployments[-15:]):
            ts   = d.get("timestamp", "?")[:16].replace("T", " ")
            ok   = "[OK]  " if d.get("success") else "[FAIL]"
            svcs = ",".join(d.get("services", []))
            ag   = d.get("agent", "?")
            sha  = d.get("commit", "?")[:10]
            nc   = d.get("commit_count", 0)
            dur  = f"{d.get('duration_s', 0):.0f}s"
            print(f"  {ok} {ts}  {sha}  {ag:<18}  {nc} commit(s)  [{svcs}]  {dur}")

    # Also fetch remote log
    print(f"\n  Remote VPS log:")
    raw = ssh_out(f"cat {REMOTE_LOG} 2>/dev/null || echo '[]'")
    try:
        remote = json.loads(raw)
        for d in reversed(remote[-5:]):
            ts  = d.get("timestamp", "?")[:16].replace("T", " ")
            ok  = "[OK]  " if d.get("success") else "[FAIL]"
            ag  = d.get("agent", "?")
            sha = d.get("commit", "?")[:10]
            print(f"  {ok} {ts}  {sha}  {ag}")
    except Exception:
        print("  (could not read remote log)")
    print()


def cmd_status():
    print("\n  VPS Service Status:\n")
    out = ssh_out(f"cd {VPS_APP} && docker compose ps")
    for line in out.splitlines():
        print(f"  {line}")
    lock = ssh_out(f"cat {LOCK_PATH} 2>/dev/null || echo none")
    print(f"\n  Deploy lock: {lock}")
    head = ssh_out(f"cd {VPS_APP} && git log --oneline -3")
    print(f"\n  VPS HEAD:\n  {head.replace(chr(10), chr(10)+'  ')}\n")


def cmd_health():
    print("\n  Running health check...\n")
    ok, lines = run_health_check()
    for l in lines:
        print(l)
    print(f"\n  Overall: {'HEALTHY' if ok else 'DEGRADED'}\n")


def cmd_rollback(state: dict, agent: str, dry_run: bool):
    deployments = state.get("deployments", [])
    if len(deployments) < 2:
        print("  Not enough history to rollback (need at least 2 deploys).")
        return 1
    target = deployments[-2]
    commit = target.get("commit", "")
    print(f"\n  Rolling back to commit {commit} ({target.get('timestamp','?')[:16]})")
    if dry_run:
        print("  [DRY RUN] No changes made.\n")
        return 0
    if not acquire_lock(agent):
        print("  Lock busy — use --force to override.")
        return 1
    try:
        ssh(f"cd {VPS_APP} && git fetch origin && git checkout {commit}", check=False, capture=False)
        ssh(f"cd {VPS_APP} && docker compose up -d --build 2>&1 | tail -20", capture=False)
        print("  Rollback complete.\n")
    finally:
        release_lock()
    return 0


# ─── Main deploy ──────────────────────────────────────────────────────────────

def cmd_deploy(args, state: dict) -> int:
    t_start = time.time()

    print(f"\n{'═'*62}")
    print(f"  CAD Digitizer — Deployer Agent")
    print(f"  Triggered by : {args.agent}")
    print(f"  Time         : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'═'*62}\n")

    # ── Sync with remote ──────────────────────────────────────────────────────
    print("  Checking remote state...")
    remote_head = fetch_remote()
    local_head  = current_commit()
    last_deploy = state.get("last_deployed_commit")

    print(f"  Local HEAD     : {local_head[:12]}")
    print(f"  Remote HEAD    : {remote_head[:12]}")
    print(f"  Last deployed  : {last_deploy[:12] if last_deploy else 'never'}")

    if remote_head != local_head:
        print(f"\n  Remote has newer commits — pulling...")
        _run("git pull origin master", capture=False)
        local_head = current_commit()
        print(f"  Pulled to {local_head[:12]}")

    # ── Determine what changed ────────────────────────────────────────────────
    commits      = commits_between(last_deploy, local_head)
    changed      = changed_files_between(last_deploy, local_head)

    if not commits and not args.force:
        print("\n  Nothing new to deploy — VPS is current.")
        print("  Running health check anyway...")
        ok, lines = run_health_check()
        for l in lines:
            print(l)
        if not ok:
            print("\n  Unhealthy services detected — use --force to redeploy.\n")
        else:
            print("\n  All services healthy.\n")
        return 0 if ok else 1

    if args.services:
        affected = args.services
    elif args.force and not commits:
        affected = ALL_BUILDABLE[:]
    else:
        affected = detect_services(changed)

    # ── Show summary ─────────────────────────────────────────────────────────
    if commits:
        print(f"\n  {len(commits)} commit(s) pending deploy:\n")
        authors: dict[str, int] = {}
        for c in commits:
            print(f"    {c['hash'][:10]}  {c['author']:<20}  {c['message'][:52]}")
            authors[c['author']] = authors.get(c['author'], 0) + 1

        if len(authors) > 1:
            print(f"\n  Multi-agent batch — contributors:")
            for author, n in sorted(authors.items(), key=lambda x: -x[1]):
                print(f"    {n:2d} commit(s)  {author}")

        print(f"\n  Changed files  : {len(changed)}")

    print(f"  Services to rebuild: {', '.join(affected)}")

    if args.dry_run:
        print(f"\n  [DRY RUN] Would rebuild: {', '.join(affected)}")
        print("  [DRY RUN] No changes made.\n")
        return 0

    # ── Pre-deploy checks ─────────────────────────────────────────────────────
    print(f"\n  Pre-deploy checks...")
    _pre_checks(affected)

    # ── Acquire lock ──────────────────────────────────────────────────────────
    print(f"\n  Acquiring deploy lock on VPS...")
    if not acquire_lock(args.agent, force=args.force):
        lock_info = ssh_out(f"cat {LOCK_PATH} 2>/dev/null", default="unknown")
        print(f"  BLOCKED — deploy already in progress: {lock_info[:120]}")
        print("  Wait for it to finish or use --force to override.\n")
        return 1
    print("  Lock acquired.")

    try:
        # ── Pull on VPS ───────────────────────────────────────────────────────
        print(f"\n  Pulling on VPS...")
        pull_out = ssh_out(f"cd {VPS_APP} && git pull origin master 2>&1")
        for line in pull_out.splitlines()[-6:]:
            print(f"    {line}")

        vps_head = ssh_out(f"cd {VPS_APP} && git rev-parse HEAD")
        print(f"  VPS now at: {vps_head[:12]}")

        # ── Selective rebuild ─────────────────────────────────────────────────
        svc_str = " ".join(affected)
        print(f"\n  Building: {svc_str}")
        print(f"  {'─'*58}")
        ssh(f"cd {VPS_APP} && docker compose up -d --build {svc_str} 2>&1 | tail -40",
            capture=False, check=True)

        # ── Health check ──────────────────────────────────────────────────────
        print(f"\n  Waiting {HEALTH_SETTLE_S}s for services to settle...")
        time.sleep(HEALTH_SETTLE_S)

        healthy, health_lines = run_health_check()
        print(f"\n  Health check:")
        for l in health_lines:
            print(l)

        duration = time.time() - t_start
        record = {
            "timestamp":    datetime.now(timezone.utc).isoformat(),
            "agent":        args.agent,
            "commit":       local_head[:12],
            "services":     affected,
            "commit_count": len(commits),
            "authors":      list({c["author"] for c in commits}),
            "success":      healthy,
            "duration_s":   round(duration, 1),
        }

        if not healthy:
            print(f"\n  Health check FAILED after {duration:.0f}s — attempting auto-rollback...")
            prev = state.get("last_deployed_commit")
            if prev:
                ssh(f"cd {VPS_APP} && git checkout {prev} && "
                    f"docker compose up -d --build {svc_str} 2>&1 | tail -10",
                    check=False, capture=False)
                print("  Rolled back to previous commit. Verify manually.")
            record["success"] = False
            _persist(state, record)
            return 1

        # ── Persist success ───────────────────────────────────────────────────
        state["last_deployed_commit"] = local_head
        _persist(state, record)

        print(f"\n{'═'*62}")
        print(f"  DEPLOY COMPLETE")
        print(f"  Commit   : {local_head[:12]}")
        print(f"  Services : {svc_str}")
        print(f"  Duration : {duration:.0f}s")
        print(f"{'═'*62}\n")
        return 0

    except Exception as e:
        print(f"\n  DEPLOY FAILED: {e}\n")
        return 1

    finally:
        release_lock()


def _pre_checks(services: list[str]):
    # TypeScript (only if frontend is being built)
    if "frontend" in services:
        fe_dir = REPO_ROOT / "frontend"
        if fe_dir.exists():
            r = _run("npx tsc --noEmit 2>&1", cwd=fe_dir, check=False)
            ts_errors = [l for l in (r.stdout + r.stderr).splitlines() if "error TS" in l]
            if ts_errors:
                print(f"  WARN  TypeScript: {len(ts_errors)} error(s) (first 3 shown):")
                for e in ts_errors[:3]:
                    print(f"        {e.strip()}")
            else:
                print(f"  OK    TypeScript")

    # Python syntax (only if python-worker is being built)
    if "python-worker" in services:
        py_dir = REPO_ROOT / "backend-python"
        py_files = list(py_dir.rglob("*.py")) if py_dir.exists() else []
        bad = []
        for pf in py_files[:80]:
            r = _run(f'python -m py_compile "{pf}"', check=False)
            if r.returncode != 0:
                bad.append(pf.name)
        if bad:
            print(f"  WARN  Python syntax errors: {', '.join(bad[:5])}")
        else:
            print(f"  OK    Python syntax ({len(py_files)} files)")


def _persist(state: dict, record: dict):
    state.setdefault("deployments", []).append(record)
    state["deployments"] = state["deployments"][-30:]
    save_state(state)
    append_remote_log(record)


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(
        description="Smart multi-source deployer for CAD Digitizer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--dry-run",  action="store_true", help="Show plan without deploying")
    p.add_argument("--force",    action="store_true", help="Skip lock + redeploy even if current")
    p.add_argument("--agent",    default=os.environ.get("AGENT_NAME", "ClaudeCode"),
                   help="Name/ID of the agent or person triggering this deploy")
    p.add_argument("--services", nargs="*", metavar="SVC",
                   choices=ALL_BUILDABLE + [None],  # type: ignore
                   help=f"Rebuild only these services: {ALL_BUILDABLE}")
    p.add_argument("--history",  action="store_true", help="Show deploy history and exit")
    p.add_argument("--status",   action="store_true", help="Show live VPS status and exit")
    p.add_argument("--health",   action="store_true", help="Run health check only")
    p.add_argument("--rollback", action="store_true", help="Rollback to previous deploy")
    args = p.parse_args()

    state = load_state()

    if args.history:
        cmd_history(state)
        return 0
    if args.status:
        cmd_status()
        return 0
    if args.health:
        cmd_health()
        return 0
    if args.rollback:
        return cmd_rollback(state, args.agent, args.dry_run)

    return cmd_deploy(args, state)


if __name__ == "__main__":
    sys.exit(main())
