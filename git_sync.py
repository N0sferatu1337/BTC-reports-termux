#!/usr/bin/env python3
"""
git_sync.py - veröffentlicht Marktberichte im Branch "reports".

Der Branch "main" wird nicht automatisch verändert (Code bleibt manuell versioniert).
Die Berichte liegen in einem Git-Worktree, der auf dem Branch "reports" ausgecheckt ist.
Dadurch bleibt dein Arbeitsstand auf "main" unberührt.
"""

import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

log = logging.getLogger("git_sync")


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)


def _remote_branch_exists(repo: Path, remote: str, branch: str) -> bool:
    _git(repo, "fetch", remote, branch)  # Fehler ignorieren: Branch existiert evtl. noch nicht
    return _git(repo, "rev-parse", "--verify", "-q", f"{remote}/{branch}").returncode == 0


def ensure_reports_worktree(
    repo: Path, worktree: Path, branch: str = "reports", remote: str = "origin"
) -> bool:
    """Legt den Worktree für den Reports-Branch an, falls er noch nicht existiert."""
    worktree = Path(worktree)
    if (worktree / ".git").exists():
        return True
    if worktree.exists() and any(worktree.iterdir()):
        log.error("%s existiert, ist aber kein Worktree. Bitte Ordner prüfen.", worktree)
        return False

    if _remote_branch_exists(repo, remote, branch):
        res = _git(repo, "worktree", "add", "-B", branch, str(worktree), f"{remote}/{branch}")
    else:
        # Neuer, leerer Branch ohne Vorgeschichte (benötigt Git >= 2.42)
        res = _git(repo, "worktree", "add", "--orphan", "-b", branch, str(worktree))

    if res.returncode != 0:
        log.error("Worktree für Branch %s konnte nicht angelegt werden: %s", branch, res.stderr.strip())
        return False
    log.info("Reports-Worktree bereit: %s", worktree)
    return True


def sync_reports(
    worktree: Path,
    reports_subdir: str = "reports",
    remote: str = "origin",
    branch: str = "reports",
    timestamp: Optional[datetime] = None,
) -> bool:
    """Committet neue Berichtsdateien im Worktree und veröffentlicht den Branch."""
    worktree = Path(worktree)
    stamp = (timestamp or datetime.now()).strftime("%Y-%m-%d %H:%M")

    if _git(worktree, "status", "--porcelain", "--", reports_subdir).stdout.strip():
        for step in (
            ("add", "--", reports_subdir),
            ("commit", "-m", f"chore(report): Marktbericht {stamp}"),
        ):
            res = _git(worktree, *step)
            if res.returncode != 0:
                log.error("Schritt %s fehlgeschlagen: %s", step[0], (res.stderr or res.stdout).strip())
                return False
        log.info("Commit für Bericht %s erstellt.", stamp)
    else:
        log.info("Keine neuen Berichte. Prüfe auf ausstehende Commits.")

    if _remote_branch_exists(worktree, remote, branch):
        sync = _git(worktree, "pull", "--rebase", remote, branch)
        if sync.returncode != 0:
            log.error("Rebase mit %s/%s fehlgeschlagen: %s", remote, branch, sync.stderr.strip())
            _git(worktree, "rebase", "--abort")
            return False

    push = _git(worktree, "push", "-u", remote, branch)
    if push.returncode != 0:
        log.error("Veröffentlichung fehlgeschlagen: %s", push.stderr.strip())
        return False

    log.info("Bericht nach %s/%s veröffentlicht.", remote, branch)
    return True
