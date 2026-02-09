"""Theme Manager (Profiles via JSON + Override)

Ziele:
- Im Code nur 2 Fallback-Themes (Standard Hell/Dunkel)
- Alle weiteren Profile werden als JSON aus ./views/profiles geladen (mitgeliefert)
- Benutzer-Änderungen werden als Override unter ~/.budgetmanager/profiles gespeichert

Damit:
- keine "Theme-Farbexplosion" durch kaputte Live-Save-Events
- saubere Nachvollziehbarkeit: welche JSON macht Probleme
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json
import re

from PySide6.QtWidgets import QApplication


@dataclass
class ThemeProfile:
    name: str
    data: Dict[str, Any]

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.data)


def _slugify(name: str) -> str:
    s = name.strip().lower()
    # Normalisieren
    s = s.replace("–", "-").replace("—", "-")
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^a-z0-9_\-]", "", s)
    s = s.replace("-", "_")
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "profile"


def _is_hex_color(v: str) -> bool:
    if not isinstance(v, str):
        return False
    return bool(re.fullmatch(r"#[0-9a-fA-F]{6}", v.strip()))


# Nur 2 Fallback-Profile im Code (wie gewünscht)
BUILTIN_PROFILES: Dict[str, Dict[str, Any]] = {
    "Standard Hell": {
        "modus": "hell",
        "hintergrund_app": "#ffffff",
        "hintergrund_panel": "#f6f7f9",
        "hintergrund_seitenleiste": "#f0f2f5",
        "text": "#111111",
        "text_gedimmt": "#444444",
        "akzent": "#2f80ed",
        "tabelle_hintergrund": "#ffffff",
        "tabelle_alt": "#f7f9fc",
        "tabelle_header": "#eef2f7",
        "tabelle_gitter": "#d6dbe3",
        "auswahl_hintergrund": "#2f80ed",
        "auswahl_text": "#ffffff",
        "negativ_text": "#e74c3c",
        "typ_einnahmen": "#2ecc71",
        "typ_ausgaben": "#e74c3c",
        "typ_ersparnisse": "#3498db",
        "schriftgroesse": 10,
        "dropdown_bg": "#ffffff",
        "dropdown_text": "#111111",
        "dropdown_selection": "#2f80ed",
        "dropdown_selection_text": "#ffffff",
        "dropdown_border": "#d6dbe3",
    },
    "Standard Dunkel": {
        "modus": "dunkel",
        "hintergrund_app": "#1e1e1e",
        "hintergrund_panel": "#2d2d30",
        "hintergrund_seitenleiste": "#252526",
        "text": "#cccccc",
        "text_gedimmt": "#808080",
        "akzent": "#007acc",
        "tabelle_hintergrund": "#1e1e1e",
        "tabelle_alt": "#252526",
        "tabelle_header": "#2d2d30",
        "tabelle_gitter": "#3e3e42",
        "auswahl_hintergrund": "#007acc",
        "auswahl_text": "#ffffff",
        "negativ_text": "#f48771",
        "typ_einnahmen": "#4ec9b0",
        "typ_ausgaben": "#f48771",
        "typ_ersparnisse": "#569cd6",
        "schriftgroesse": 10,
        "dropdown_bg": "#2d2d30",
        "dropdown_text": "#cccccc",
        "dropdown_selection": "#007acc",
        "dropdown_selection_text": "#ffffff",
        "dropdown_border": "#3e3e42",
    },
}

# Kompatibilität: alte Namen → neue Namen (falls Einstellungen noch alte Werte enthalten)
ALIASES: Dict[str, str] = {
    "Solarized Hell": "Solarized - Hell",
    "Solarized Dunkel": "Solarized - Dunkel",
    "Nord Dunkel": "Nord - Dunkel",
    "Dracula Dunkel": "Dracula - Dunkel",
    "Gruvbox Hell": "Gruvbox - Hell",
    "Gruvbox Dunkel": "Gruvbox - Dunkel",
    "Monokai Dunkel": "Monokai - Dunkel",
}


class ThemeManager:
    def __init__(self, settings):
        self.settings = settings

        # Mitgelieferte Profile (Release)
        self.bundled_dir = Path(__file__).resolve().parent / "views" / "profiles"

        # User-Overrides
        self.user_dir = Path.home() / ".budgetmanager" / "profiles"
        self.user_dir.mkdir(parents=True, exist_ok=True)

        self._current_profile: Optional[ThemeProfile] = None

        # Cache
        self._bundled_index: Dict[str, Path] = {}
        self._user_index: Dict[str, Path] = {}
        self._errors: List[Tuple[str, str, str]] = []  # (profile_name, path, error)

        self.rescan_profiles()

    # -------------------------
    # Profil-Discovery / Errors
    # -------------------------

    def get_load_errors(self) -> List[Tuple[str, str, str]]:
        """Liste der Probleme beim Laden (Name, Pfad, Fehlermeldung)."""
        return list(self._errors)

    def rescan_profiles(self) -> None:
        self._bundled_index.clear()
        self._user_index.clear()
        self._errors.clear()

        self._scan_dir(self.bundled_dir, target=self._bundled_index)
        self._scan_dir(self.user_dir, target=self._user_index)

        # Builtins sicherstellen
        for name in BUILTIN_PROFILES.keys():
            if name not in self._bundled_index and name not in self._user_index:
                # builtins werden nicht indiziert – erscheinen aber in get_all_profiles
                pass

    def _scan_dir(self, directory: Path, target: Dict[str, Path]) -> None:
        if not directory.exists():
            return

        for file in sorted(directory.glob("*.json")):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    raw = json.load(f)

                name = str(raw.get("name") or "").strip()
                if not name:
                    # Fallback aus Filename
                    name = file.stem.replace("_", " ").strip()

                data = dict(raw)
                data.pop("name", None)

                ok, msg = self._validate_profile_data(data)
                if not ok:
                    self._errors.append((name, str(file), msg))
                    continue

                target[name] = file

            except Exception as e:
                # file.stem als best-effort name
                name = file.stem.replace("_", " ").strip()
                self._errors.append((name, str(file), f"JSON-Ladefehler: {e}"))

    def _validate_profile_data(self, data: Dict[str, Any]) -> Tuple[bool, str]:
        mode = str(data.get("modus", "hell")).strip().lower()
        if mode not in ("hell", "dunkel"):
            return False, f"Ungültiger modus: {mode}"

        fs = data.get("schriftgroesse", 10)
        try:
            fs_i = int(fs)
        except Exception:
            return False, f"Ungültige schriftgroesse: {fs}"
        if fs_i < 6 or fs_i > 30:
            return False, f"schriftgroesse außerhalb Range: {fs_i}"

        # Farbfelder prüfen (wenn vorhanden)
        for k, v in data.items():
            if k in ("modus", "schriftgroesse"):
                continue
            if k.startswith("_"):
                continue
            if isinstance(v, str) and v.strip().startswith("#"):
                if not _is_hex_color(v):
                    return False, f"Ungültige Farbe {k}={v}"

        return True, ""

    # -------------------------
    # Public API
    # -------------------------

    def get_all_profiles(self) -> List[str]:
        # Union + builtins
        names = set(self._bundled_index.keys()) | set(self._user_index.keys()) | set(BUILTIN_PROFILES.keys())
        # Aliases NICHT extra anzeigen
        names = {n for n in names if n not in ALIASES.keys()}
        return sorted(names, key=lambda s: s.casefold())

    def has_override(self, name: str) -> bool:
        name = self._resolve_alias(name)
        return name in self._user_index

    def is_bundled(self, name: str) -> bool:
        name = self._resolve_alias(name)
        return name in self._bundled_index

    def _resolve_alias(self, name: str) -> str:
        name = (name or "").strip()
        return ALIASES.get(name, name)

    def get_profile(self, name: str) -> Optional[ThemeProfile]:
        name = self._resolve_alias(name)

        # User Override zuerst
        p = self._user_index.get(name)
        if p:
            data = self._load_json_file(p)
            if data is not None:
                return ThemeProfile(name=name, data=data)

        # Bundled
        p = self._bundled_index.get(name)
        if p:
            data = self._load_json_file(p)
            if data is not None:
                return ThemeProfile(name=name, data=data)

        # Builtins
        base = BUILTIN_PROFILES.get(name)
        if base:
            return ThemeProfile(name=name, data=dict(base))

        return None

    def _load_json_file(self, path: Path) -> Optional[Dict[str, Any]]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            raw.pop("name", None)
            if not isinstance(raw, dict):
                return None
            ok, _ = self._validate_profile_data(raw)
            if not ok:
                return None
            return raw
        except Exception:
            return None

    def update_profile(self, name: str, data: Dict[str, Any]) -> bool:
        """Speichert IMMER als User-Override (kein Profil-Spam)."""
        name = self._resolve_alias(name)

        # Validieren
        ok, msg = self._validate_profile_data(data)
        if not ok:
            # Fehler auch in log schreiben
            self._append_error_log(name, str(self.user_dir / f"{_slugify(name)}.json"), msg)
            return False

        path = self.user_dir / f"{_slugify(name)}.json"
        payload = {"name": name, **data}

        try:
            tmp = path.with_suffix(".json.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            tmp.replace(path)

            # Re-Index
            self._user_index[name] = path
            return True
        except Exception as e:
            self._append_error_log(name, str(path), f"Save-Fehler: {e}")
            return False

    def delete_profile(self, name: str) -> bool:
        """Löscht ein Profil.

        - Wenn Override existiert: löscht Override.
        - Bundled Profile werden NICHT gelöscht (nur Override).
        """
        name = self._resolve_alias(name)
        p = self._user_index.get(name)
        if not p:
            return False
        try:
            p.unlink(missing_ok=True)
            self._user_index.pop(name, None)
            # wenn aktuelles Profil: fallback setzen
            if self.settings.get("active_design_profile") == name:
                fallback = "Standard Dunkel" if self._current_mode() == "dunkel" else "Standard Hell"
                self.settings.set("active_design_profile", fallback)
                self._current_profile = None
            return True
        except Exception as e:
            self._append_error_log(name, str(p), f"Delete-Fehler: {e}")
            return False

    def reset_profile(self, name: str) -> bool:
        """Zurücksetzen:
        - Bei Bundled Profile: Override löschen (falls vorhanden)
        - Bei Builtin only: Override löschen und builtins verwenden
        """
        name = self._resolve_alias(name)
        if name in self._user_index:
            return self.delete_profile(name)
        return True

    def set_current_profile(self, name: str) -> bool:
        profile = self.get_profile(name)
        if profile:
            self._current_profile = profile
            self.settings.set("active_design_profile", profile.name)
            return True
        return False

    def get_current_profile(self) -> Optional[ThemeProfile]:
        if not self._current_profile:
            saved = (self.settings.get("active_design_profile") or "").strip() or "Standard Hell"
            # Alias ggf. auflösen
            saved = self._resolve_alias(saved)
            if not self.set_current_profile(saved):
                # fallback
                self.set_current_profile("Standard Hell")
        return self._current_profile

    def _current_mode(self) -> str:
        # Versuche SettingsDialog / Settings kompatibel
        v = (self.settings.get("theme") if hasattr(self.settings, "get") else None) or "light"
        if isinstance(v, str) and v.lower() in ("dark", "dunkel"):
            return "dunkel"
        return "hell"

    def get_type_colors(self) -> Dict[str, str]:
        p = self.get_current_profile()
        if not p:
            return {"Einnahmen": "#2ecc71", "Ausgaben": "#e74c3c", "Ersparnisse": "#3498db"}
        return {
            "Einnahmen": p.get("typ_einnahmen", "#2ecc71"),
            "Einkommen": p.get("typ_einnahmen", "#2ecc71"),
            "Ausgaben": p.get("typ_ausgaben", "#e74c3c"),
            "Ersparnisse": p.get("typ_ersparnisse", "#3498db"),
        }

    def build_stylesheet(self, profile: ThemeProfile) -> str:
        p = profile.data
        bg_app = p.get("hintergrund_app", "#fff")
        bg_panel = p.get("hintergrund_panel", "#f6f7f9")
        text = p.get("text", "#111")
        text_dim = p.get("text_gedimmt", "#666")
        accent = p.get("akzent", "#2f80ed")
        table_bg = p.get("tabelle_hintergrund", "#fff")
        table_alt = p.get("tabelle_alt", "#f7f9fc")
        table_header = p.get("tabelle_header", "#eef2f7")
        table_grid = p.get("tabelle_gitter", "#d6dbe3")
        sel_bg = p.get("auswahl_hintergrund", accent)
        sel_text = p.get("auswahl_text", "#fff")

        dropdown_bg = p.get("dropdown_bg", bg_panel)
        dropdown_text = p.get("dropdown_text", text)
        dropdown_sel = p.get("dropdown_selection", accent)
        dropdown_sel_text = p.get("dropdown_selection_text", "#fff")
        dropdown_border = p.get("dropdown_border", table_grid)

        font_size = p.get("schriftgroesse", 10)

        return f"""
* {{ font-size: {font_size}pt; }}
QMainWindow, QDialog, QWidget {{ background-color: {bg_app}; color: {text}; }}
QLabel {{ color: {text}; }}
QPushButton {{ background-color: {accent}; color: #fff; border: none; padding: 8px 16px; border-radius: 6px; }}
QPushButton:hover {{ background-color: {accent}aa; }}
QLineEdit, QTextEdit, QSpinBox, QDateEdit {{ background-color: {bg_panel}; color: {text}; border: 1px solid {table_grid}; border-radius: 4px; padding: 6px; }}
QComboBox {{ background-color: {dropdown_bg}; color: {dropdown_text}; border: 1px solid {dropdown_border}; border-radius: 4px; padding: 6px; min-height: 20px; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{ background-color: {dropdown_bg}; color: {dropdown_text}; border: 1px solid {dropdown_border}; selection-background-color: {dropdown_sel}; selection-color: {dropdown_sel_text}; }}
QComboBox QAbstractItemView::item {{ padding: 6px; min-height: 24px; background-color: {dropdown_bg}; color: {dropdown_text}; }}
QComboBox QAbstractItemView::item:selected {{ background-color: {dropdown_sel}; color: {dropdown_sel_text}; }}
QTableWidget {{ background-color: {table_bg}; alternate-background-color: {table_alt}; gridline-color: {table_grid}; selection-background-color: {sel_bg}; selection-color: {sel_text}; }}
	/* WICHTIG: Kategorien-Tab nutzt QTreeWidget. Ohne explizites Styling nimmt Qt Default-Palette,
	   was bei hellen Profilen zu extrem dunklen Zebra-Streifen führt. */
	QTreeWidget, QTreeView {{
		background-color: {table_bg};
		alternate-background-color: {table_alt};
		border: 1px solid {table_grid};
		color: {text};
		selection-background-color: {sel_bg};
		selection-color: {sel_text};
		outline: 0;
	}}
	QTreeWidget::item, QTreeView::item {{ padding: 4px 6px; }}
	QTreeWidget::item:alternate, QTreeView::item:alternate {{ background-color: {table_alt}; }}
	QTreeWidget::item:selected, QTreeView::item:selected {{ background-color: {sel_bg}; color: {sel_text}; }}
QHeaderView::section {{ background-color: {table_header}; border: 1px solid {table_grid}; padding: 6px; }}
QGroupBox {{ background-color: {bg_panel}; border: 1px solid {table_grid}; border-radius: 8px; padding: 12px; margin-top: 12px; }}
QGroupBox::title {{ color: {accent}; padding: 0 8px; }}

QTabWidget::pane {{ border: 1px solid {table_grid}; border-radius: 10px; }}
QTabBar::tab {{ background-color: {bg_panel}; color: {text}; padding: 8px 14px; margin: 2px; border-radius: 10px; border: 1px solid {table_grid}; }}
QTabBar::tab:selected {{ background-color: {accent}; color: #fff; border: 1px solid {accent}; }}
QTabBar::tab:hover {{ background-color: {accent}22; }}

QMenuBar {{ background-color: {bg_panel}; color: {text}; }}
QMenuBar::item:selected {{ background-color: {accent}; color: #fff; border-radius: 6px; }}
QMenu {{ background-color: {bg_panel}; color: {text}; border: 1px solid {table_grid}; }}
QMenu::item:selected {{ background-color: {accent}; color: #fff; }}
"""

    def apply_theme(self, app=None, profile_name=None):
        if app is None:
            app = QApplication.instance()

        if profile_name:
            self.set_current_profile(profile_name)

        profile = self.get_current_profile()
        if profile and app:
            app.setStyleSheet(self.build_stylesheet(profile))
            # Typfarben auch weiterhin in Settings schreiben
            self.settings.set("typ_einnahmen_color", profile.get("typ_einnahmen", "#2ecc71"))
            self.settings.set("typ_ausgaben_color", profile.get("typ_ausgaben", "#e74c3c"))
            self.settings.set("typ_ersparnisse_color", profile.get("typ_ersparnisse", "#3498db"))

    # -------------------------
    # Logging
    # -------------------------

    def _append_error_log(self, name: str, path: str, msg: str) -> None:
        try:
            log_path = Path.home() / ".budgetmanager" / "theme_profile_errors.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[{name}] {path}: {msg}\n")
        except Exception:
            pass
