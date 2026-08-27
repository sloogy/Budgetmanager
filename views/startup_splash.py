"""Startbildschirm, der die Zeit bis zum fertigen Hauptfenster ueberbrueckt.

Der Start des BudgetManagers ist keine gerade Linie: zwischen ``QApplication``
und ``MainWindow.show()`` koennen Sprachauswahl, Anmeldedialog, Erststart-
Assistent, Migrationshinweise und Fehlermeldungen liegen. Ein Splash, der
stumpf bis zum Hauptfenster stehen bleibt, wuerde genau ueber diesen Dialogen
kleben — schlimmer als gar kein Splash.

Deshalb beobachtet dieses Modul die Anwendung: sobald ein modales Fenster
sichtbar wird, verschwindet der Splash; ist das letzte modale Fenster wieder
zu, kommt er zurueck. Zusaetzlich sichern zwei Notbremsen ab, dass er nie
haengen bleibt:

* ein Watchdog-Timer schliesst ihn nach :data:`WATCHDOG_MS` in jedem Fall,
* :meth:`StartupSplash.close_active` schliesst ihn aus jedem Fehlerpfad,
  ohne dass der Aufrufer eine Referenz halten muss.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtWidgets import QSplashScreen, QWidget

from utils.branding import logo_pixmap

logger = logging.getLogger(__name__)

# Logische Fensterbreite des Splash. Das ausgelieferte Banner ist randlos
# zugeschnitten (rund 1965x450), daraus werden etwa 560x128 Punkte — gross
# genug zum Lesen, klein genug, um nicht zu stoeren.
SPLASH_WIDTH = 560

# Absolute Obergrenze. Auch wenn jeder regulaere Schliesspfad ausfaellt, ist
# der Splash spaetestens danach weg.
WATCHDOG_MS = 30_000


class _ModalWatcher(QObject):
    """Blendet den Splash aus, solange irgendein modales Fenster offen ist."""

    def __init__(self, splash: StartupSplash, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._splash = splash
        self._open_modals: set[int] = set()

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        event_type = event.type()
        if event_type not in (QEvent.Show, QEvent.Hide):
            return False
        if not isinstance(obj, QWidget):
            return False
        try:
            if not obj.isWindow() or obj is self._splash.widget():
                return False
            if event_type == QEvent.Show and obj.isModal():
                self._open_modals.add(id(obj))
            else:
                self._open_modals.discard(id(obj))
        except RuntimeError:
            # Widget bereits zerstoert – dann zaehlt es auch nicht mehr mit.
            self._open_modals.discard(id(obj))
        self._splash.set_suspended(bool(self._open_modals))
        return False


class StartupSplash:
    """Duenne Huelle um :class:`QSplashScreen`, tolerant gegen fehlendes Bild.

    Alle Methoden sind auch dann gefahrlos aufrufbar, wenn kein Logo gefunden
    wurde oder der Splash schon geschlossen ist. Die Aufrufstelle im Start
    braucht deshalb keine Fallunterscheidung.
    """

    _active: StartupSplash | None = None

    def __init__(self, splash: QSplashScreen | None) -> None:
        self._splash = splash
        self._suspended = False
        self._closed = False
        self._app: QObject | None = None
        self._watcher: _ModalWatcher | None = None
        self._watchdog: QTimer | None = None

    # ── Erzeugung ────────────────────────────────────────────────

    @classmethod
    def start(cls, app, *, width: int = SPLASH_WIDTH) -> StartupSplash:
        """Zeigt den Splash sofort an und gibt die Steuerung zurueck."""
        cls.close_active()
        instance = cls(cls._build_widget(app, width))
        instance._install_watchers(app)
        cls._active = instance
        return instance

    @staticmethod
    def _build_widget(app, width: int) -> QSplashScreen | None:
        pixmap = logo_pixmap(width, device_pixel_ratio=_screen_ratio(app))
        if pixmap is None:
            logger.debug("Kein Logo-Banner gefunden – Start ohne Splash.")
            return None
        splash = QSplashScreen(pixmap, Qt.WindowStaysOnTopHint)
        # Das Banner ist transparent; ohne dieses Attribut malte Qt eine
        # undurchsichtige Flaeche hinter das freigestellte Motiv.
        splash.setAttribute(Qt.WA_TranslucentBackground, True)
        splash.setEnabled(False)  # nimmt keine Eingaben an
        splash.show()
        try:
            app.processEvents()
        except (RuntimeError, AttributeError) as exc:
            logger.debug("processEvents beim Splash-Start fehlgeschlagen: %s", exc)
        return splash

    def _install_watchers(self, app) -> None:
        if self._splash is None:
            return
        self._app = app
        self._watcher = _ModalWatcher(self, self._splash)
        try:
            app.installEventFilter(self._watcher)
        except (RuntimeError, AttributeError) as exc:
            logger.debug("Splash-Eventfilter nicht installierbar: %s", exc)
            self._watcher = None

        watchdog = QTimer(self._splash)
        watchdog.setSingleShot(True)
        watchdog.timeout.connect(self._on_watchdog)
        watchdog.start(WATCHDOG_MS)
        self._watchdog = watchdog

    # ── Zustand ──────────────────────────────────────────────────

    def widget(self) -> QSplashScreen | None:
        return self._splash

    def is_visible(self) -> bool:
        if self._closed or self._splash is None:
            return False
        try:
            return bool(self._splash.isVisible())
        except RuntimeError:
            return False

    def set_suspended(self, suspended: bool) -> None:
        """Blendet den Splash aus/ein, ohne ihn endgueltig zu schliessen."""
        if self._closed or self._splash is None:
            return
        suspended = bool(suspended)
        if suspended == self._suspended:
            return
        self._suspended = suspended
        try:
            if suspended:
                self._splash.hide()
            else:
                self._splash.show()
        except RuntimeError:
            self._closed = True

    # ── Beenden ──────────────────────────────────────────────────

    def _on_watchdog(self) -> None:
        if not self._closed:
            logger.warning(
                "Startbildschirm nach %s ms zwangsweise geschlossen.", WATCHDOG_MS
            )
        self.close()

    def finish(self, window: QWidget | None) -> None:
        """Uebergibt an das fertige Hauptfenster und schliesst den Splash."""
        if self._splash is not None and not self._closed and window is not None:
            try:
                self._splash.finish(window)
            except (RuntimeError, TypeError) as exc:
                logger.debug("Splash-finish fehlgeschlagen: %s", exc)
        self.close()

    def close(self) -> None:
        """Schliesst den Splash endgueltig. Mehrfach aufrufbar."""
        if self._closed:
            return
        self._closed = True
        self._teardown_watchers()
        splash, self._splash = self._splash, None
        if splash is not None:
            try:
                splash.hide()
                splash.deleteLater()
            except RuntimeError:
                pass
        if type(self)._active is self:
            type(self)._active = None

    def _teardown_watchers(self) -> None:
        if self._watchdog is not None:
            try:
                self._watchdog.stop()
            except RuntimeError:
                pass
            self._watchdog = None
        if self._watcher is not None and self._app is not None:
            try:
                self._app.removeEventFilter(self._watcher)
            except (RuntimeError, AttributeError):
                pass
        self._watcher = None
        self._app = None

    @classmethod
    def close_active(cls) -> None:
        """Schliesst einen noch offenen Splash – aus jedem Fehlerpfad nutzbar."""
        active = cls._active
        if active is not None:
            active.close()
        cls._active = None


def _screen_ratio(app) -> float:
    """Geraete-Pixelverhaeltnis des Hauptbildschirms, mit Fallback 1.0."""
    try:
        screen = app.primaryScreen()
        if screen is not None:
            return float(screen.devicePixelRatio())
    except (RuntimeError, AttributeError, TypeError, ValueError):
        pass
    return 1.0
