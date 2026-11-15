import os
import subprocess
from pathlib import Path
from datetime import datetime

def sync_repository(repo_path: str = "~/crypto-bot", commit_message: str = None) -> bool:
    """
    Universeller GitOps-Automator: Staged, committet, rebaset und pusht ALLE 
    Änderungen im angegebenen Repository-Pfad, unabhängig vom Erzeuger.
    """
    target_repo = Path(repo_path).expanduser().resolve()
    
    if not (target_repo / ".git").exists():
        print(f"[GitOps Fehler] {target_repo} ist kein gültiges Git-Repository!")
        return False

    os.chdir(target_repo)
    
    # Automatischen Commit-Messsage generieren, falls keine übergeben wurde
    if not commit_message:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        commit_message = f"chore(auto-sync): update workspace at {timestamp}"

    try:
        # 1. Prüfen, ob überhaupt ungespeicherte Änderungen existieren
        status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True)
        if not status.stdout.strip():
            print("[GitOps] Keine Änderungen im Repository gefunden. Überspringe Sync.")
            return True

        # 2. Alle Änderungen (Code, Markdown, Daten) ins Staging übernehmen
        subprocess.run(["git", "add", "."], check=True)

        # 3. Lokalen Commit erstellen
        subprocess.run(["git", "commit", "-m", commit_message], check=True)

        # 4. Remote-Änderungen holen (mit Rebase, um Merge-Konflikte zu vermeiden)
        print("[GitOps] Hole Remote-Änderungen (rebase)...")
        pull_result = subprocess.run(["git", "pull", "--rebase", "origin", "main"], capture_output=True, text=True)
        
        if pull_result.returncode != 0:
            print(f"[GitOps Konflikt-Warnung]:\n{pull_result.stderr}")
            subprocess.run(["git", "rebase", "--abort"])
            return False

        # 5. Zu GitHub pushen
        print("[GitOps] Pushe Änderungen zu GitHub...")
        subprocess.run(["git", "push", "origin", "main"], capture_output=True, text=True, check=True)
        
        print("[GitOps] Erfolgreich zu GitHub synchronisiert!")
        return True

    except subprocess.CalledProcessError as e:
        print(f"[GitOps Fehler] Befehl fehlgeschlagen: {e.cmd}\n{e.stderr}")
        return False

if __name__ == "__main__":
    # Test-Aufruf direkt aus der Shell
    sync_repository()

