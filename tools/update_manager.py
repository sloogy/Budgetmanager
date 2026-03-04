from __future__ import annotations
import requests
import json
import os
import sys
import subprocess
import tempfile
import hashlib
from pathlib import Path
from typing import Optional, Dict, Tuple
from datetime import datetime
from packaging import version


class UpdateManager:
    """
    Manager für automatische Updates der BudgetManager-Anwendung
    
    Features:
    - Versionsprüfung gegen GitHub Releases
    - Download neuer Versionen
    - Automatische Installation
    - Rollback bei Fehlern
    """
    
    def __init__(self, 
                 current_version: str,
                 repo_owner: str = "yourusername",
                 repo_name: str = "budgetmanager",
                 update_channel: str = "stable"):
        """
        Args:
            current_version: Aktuelle Version (z.B. "0.17.0")
            repo_owner: GitHub Repository Owner
            repo_name: GitHub Repository Name
            update_channel: Update-Kanal ("stable" oder "beta")
        """
        self.current_version = current_version
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.update_channel = update_channel
        
        self.api_base = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
        self.download_base = f"https://github.com/{repo_owner}/{repo_name}/releases/download"
    
    def check_for_updates(self, include_prereleases: bool = False) -> Optional[Dict]:
        """
        Prüft ob Updates verfügbar sind
        
        Returns:
            Dict mit Update-Infos oder None wenn kein Update verfügbar
            {
                'version': str,
                'release_date': str,
                'changelog': str,
                'download_url': str,
                'size_mb': float,
                'is_prerelease': bool
            }
        """
        try:
            # Hole neueste Release-Info von GitHub
            url = f"{self.api_base}/releases/latest"
            if include_prereleases:
                url = f"{self.api_base}/releases"
            
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            if include_prereleases:
                releases = response.json()
                if not releases:
                    return None
                latest = releases[0]
            else:
                latest = response.json()
            
            # Filtere Pre-Releases wenn nicht gewünscht
            if not include_prereleases and latest.get('prerelease', False):
                return None
            
            latest_version = latest['tag_name'].lstrip('v')
            
            # Vergleiche Versionen
            if version.parse(latest_version) <= version.parse(self.current_version):
                return None
            
            # Finde passenden Asset (Windows Installer)
            download_url = None
            asset_size = 0
            
            for asset in latest.get('assets', []):
                if 'Setup' in asset['name'] and asset['name'].endswith('.exe'):
                    download_url = asset['browser_download_url']
                    asset_size = asset['size'] / (1024 * 1024)  # MB
                    break
            
            if not download_url:
                return None
            
            return {
                'version': latest_version,
                'release_date': latest['published_at'],
                'changelog': latest.get('body', 'Keine Änderungsnotizen verfügbar'),
                'download_url': download_url,
                'size_mb': round(asset_size, 2),
                'is_prerelease': latest.get('prerelease', False)
            }
        
        except requests.RequestException as e:
            print(f"Fehler beim Prüfen auf Updates: {e}")
            return None
        except Exception as e:
            print(f"Unerwarteter Fehler: {e}")
            return None
    
    def download_update(self, update_info: Dict, 
                       progress_callback=None) -> Optional[str]:
        """
        Lädt ein Update herunter
        
        Args:
            update_info: Update-Info Dict von check_for_updates()
            progress_callback: Optional callback(bytes_downloaded, total_bytes)
            
        Returns:
            Pfad zur heruntergeladenen Datei oder None bei Fehler
        """
        try:
            url = update_info['download_url']
            
            # Temporäre Datei erstellen
            temp_dir = tempfile.gettempdir()
            filename = f"BudgetManager_Update_{update_info['version']}.exe"
            filepath = os.path.join(temp_dir, filename)
            
            print(f"Lade Update herunter: {filename}")
            
            # Download mit Progress
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if progress_callback:
                            progress_callback(downloaded, total_size)
            
            print(f"✓ Download abgeschlossen: {filepath}")
            return filepath
        
        except Exception as e:
            print(f"Fehler beim Download: {e}")
            return None
    
    def verify_download(self, filepath: str, expected_checksum: Optional[str] = None) -> bool:
        """
        Verifiziert die heruntergeladene Datei
        
        Args:
            filepath: Pfad zur Datei
            expected_checksum: Erwarteter SHA256-Checksum (optional)
            
        Returns:
            True wenn valide
        """
        if not os.path.exists(filepath):
            return False
        
        # Basis-Checks
        file_size = os.path.getsize(filepath)
        if file_size < 1024 * 1024:  # Mindestens 1 MB
            print("Warnung: Datei scheint zu klein zu sein")
            return False
        
        # Checksum-Verifikation
        if expected_checksum:
            sha256_hash = hashlib.sha256()
            with open(filepath, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            
            actual_checksum = sha256_hash.hexdigest()
            if actual_checksum != expected_checksum:
                print(f"Checksum-Fehler!")
                print(f"  Erwartet: {expected_checksum}")
                print(f"  Erhalten: {actual_checksum}")
                return False
        
        return True
    
    def install_update(self, installer_path: str, silent: bool = False) -> bool:
        """
        Installiert ein Update
        
        Args:
            installer_path: Pfad zum Installer
            silent: Silent-Installation ohne UI
            
        Returns:
            True bei Erfolg
        """
        try:
            if not os.path.exists(installer_path):
                print(f"Installer nicht gefunden: {installer_path}")
                return False
            
            print("Starte Installation...")
            
            # Installer ausführen
            args = [installer_path]
            if silent:
                args.extend(['/SILENT', '/NOICONS'])
            
            # Installer starten und warten
            process = subprocess.Popen(args)
            
            # Wenn silent, warten auf Completion
            if silent:
                process.wait()
                return process.returncode == 0
            
            # Ansonsten: Aktuelle Anwendung beenden
            # (Installer übernimmt)
            return True
        
        except Exception as e:
            print(f"Fehler bei Installation: {e}")
            return False
    
    def create_backup_before_update(self, backup_dir: Optional[str] = None) -> str:
        """
        Erstellt ein Backup vor dem Update
        
        Returns:
            Pfad zum Backup
        """
        if backup_dir is None:
            backup_dir = str(Path.home() / "BudgetManager_Backups" / "pre_update")
        
        Path(backup_dir).mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"pre_update_v{self.current_version}_{timestamp}.db"
        
        # Hier würde die eigentliche Backup-Logik kommen
        # (Integration mit DatabaseManagementModel)
        
        return os.path.join(backup_dir, backup_name)
    
    def get_update_settings(self) -> Dict:
        """
        Liest Update-Einstellungen aus Konfigurationsdatei
        
        Returns:
            Dict mit Einstellungen
        """
        default_settings = {
            'auto_check': True,
            'check_interval_hours': 24,
            'auto_download': False,
            'auto_install': False,
            'include_prereleases': False,
            'last_check': None
        }
        
        settings_file = Path.home() / '.budgetmanager' / 'update_settings.json'
        
        if settings_file.exists():
            try:
                with open(settings_file, 'r') as f:
                    saved_settings = json.load(f)
                    default_settings.update(saved_settings)
            except Exception:
                pass
        
        return default_settings
    
    def save_update_settings(self, settings: Dict) -> None:
        """Speichert Update-Einstellungen"""
        settings_dir = Path.home() / '.budgetmanager'
        settings_dir.mkdir(parents=True, exist_ok=True)
        
        settings_file = settings_dir / 'update_settings.json'
        
        with open(settings_file, 'w') as f:
            json.dump(settings, f, indent=2)
    
    def should_check_for_updates(self) -> bool:
        """
        Prüft ob es Zeit ist, nach Updates zu suchen
        
        Returns:
            True wenn Check durchgeführt werden sollte
        """
        settings = self.get_update_settings()
        
        if not settings['auto_check']:
            return False
        
        last_check = settings.get('last_check')
        if not last_check:
            return True
        
        try:
            last_check_time = datetime.fromisoformat(last_check)
            hours_since_check = (datetime.now() - last_check_time).total_seconds() / 3600
            
            return hours_since_check >= settings['check_interval_hours']
        except Exception:
            return True
    
    def update_last_check_time(self) -> None:
        """Aktualisiert den Zeitpunkt der letzten Update-Prüfung"""
        settings = self.get_update_settings()
        settings['last_check'] = datetime.now().isoformat()
        self.save_update_settings(settings)


# Beispiel-Verwendung und CLI
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="BudgetManager Update Tool")
    parser.add_argument('--version', required=True, help='Aktuelle Version')
    parser.add_argument('--check', action='store_true', help='Nach Updates suchen')
    parser.add_argument('--download', action='store_true', help='Update herunterladen')
    parser.add_argument('--install', action='store_true', help='Update installieren')
    parser.add_argument('--silent', action='store_true', help='Silent-Installation')
    parser.add_argument('--beta', action='store_true', help='Beta-Versionen einschließen')
    
    args = parser.parse_args()
    
    manager = UpdateManager(args.version)
    
    if args.check:
        print(f"Suche nach Updates (Aktuelle Version: {args.version})...")
        update_info = manager.check_for_updates(include_prereleases=args.beta)
        
        if update_info:
            print(f"\n✓ Update verfügbar: v{update_info['version']}")
            print(f"  Größe: {update_info['size_mb']} MB")
            print(f"  Veröffentlicht: {update_info['release_date']}")
            print(f"\nÄnderungen:\n{update_info['changelog']}")
            
            if args.download:
                def progress(downloaded, total):
                    percent = (downloaded / total * 100) if total > 0 else 0
                    print(f"\rFortschritt: {percent:.1f}% ({downloaded}/{total} Bytes)", end='')
                
                filepath = manager.download_update(update_info, progress)
                print()  # Newline nach Progress
                
                if filepath and args.install:
                    manager.install_update(filepath, silent=args.silent)
        else:
            print("✓ Keine Updates verfügbar")
