"""In-App-Wissensdatenbank (Handbuch).

Ein einfacher, durchsuchbarer Themenbrowser:
- links eine Themenliste,
- oben ein Suchfeld (filtert die Themen nach Titel + Inhalt),
- rechts der Inhalt des gewählten Themas (Markdown gerendert).

Die Inhalte stehen sprachneutral in ``views/help_content.py``. Die angezeigte
Sprache richtet sich nach der App-Sprache (Fallback Deutsch).
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from utils.i18n import get_language, tr
from views.help_content import (
    HELP_FALLBACK_LANG,
    HELP_TOPICS,
    help_topic_body,
    help_topic_haystack,
    help_topic_title,
)

_ROLE_TOPIC = Qt.UserRole + 1


class HelpDialog(QDialog):
    """Durchsuchbares In-App-Handbuch."""

    def __init__(
        self,
        parent=None,
        *,
        start_topic_id: str | None = None,
        on_show_key=None,
        on_open_mindmap=None,
    ):
        super().__init__(parent)
        self._lang = self._resolve_lang()
        self._on_show_key = on_show_key
        self._on_open_mindmap = on_open_mindmap
        self.setWindowTitle(tr("help.window_title"))
        self.setMinimumSize(820, 560)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        root = QVBoxLayout(self)

        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        self.search.setPlaceholderText(tr("help.search_placeholder"))
        self.search.textChanged.connect(self._apply_filter)
        root.addWidget(self.search)

        splitter = QSplitter(Qt.Horizontal)

        left = QWidget()
        left_l = QVBoxLayout(left)
        left_l.setContentsMargins(0, 0, 0, 0)
        self.topic_list = QListWidget()
        self.topic_list.currentItemChanged.connect(self._on_topic_changed)
        left_l.addWidget(self.topic_list)
        self.empty_hint = QLabel(tr("help.no_results"))
        self.empty_hint.setWordWrap(True)
        self.empty_hint.setVisible(False)
        self.empty_hint.setStyleSheet("color: gray; padding: 6px;")
        left_l.addWidget(self.empty_hint)
        splitter.addWidget(left)

        self.viewer = QTextBrowser()
        self.viewer.setOpenExternalLinks(True)
        splitter.addWidget(self.viewer)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([240, 560])
        root.addWidget(splitter, 1)

        btn_row = QHBoxLayout()
        if callable(self._on_show_key):
            self.btn_show_key = QPushButton(tr("help.btn_show_key"))
            self.btn_show_key.clicked.connect(self._handle_show_key)
            btn_row.addWidget(self.btn_show_key)
        if callable(self._on_open_mindmap):
            self.btn_open_mindmap = QPushButton(tr("help.btn_open_mindmap"))
            self.btn_open_mindmap.clicked.connect(self._handle_open_mindmap)
            btn_row.addWidget(self.btn_open_mindmap)
        btn_row.addStretch(1)
        self.btn_close = QPushButton(tr("btn.close"))
        self.btn_close.clicked.connect(self.accept)
        btn_row.addWidget(self.btn_close)
        root.addLayout(btn_row)

        self._populate(select_id=start_topic_id)

    def _handle_open_mindmap(self) -> None:
        if callable(self._on_open_mindmap):
            try:
                self._on_open_mindmap(self)
            except Exception:
                logger.exception("Mindmap-Anzeige aus dem Handbuch fehlgeschlagen")

    def _handle_show_key(self) -> None:
        if callable(self._on_show_key):
            try:
                self._on_show_key(self)
            except Exception:
                logger.exception("Restore-Key-Anzeige aus dem Handbuch fehlgeschlagen")

    # ── intern ────────────────────────────────────────────────────
    def _resolve_lang(self) -> str:
        try:
            lang = (get_language() or HELP_FALLBACK_LANG).split("-")[0].lower()
        except Exception:
            lang = HELP_FALLBACK_LANG
        return lang

    def _populate(self, *, select_id: str | None = None) -> None:
        self.topic_list.clear()
        for topic in HELP_TOPICS:
            icon = topic.get("icon", "")
            title = help_topic_title(topic, self._lang)
            label = f"{icon}  {title}".strip()
            item = QListWidgetItem(label)
            item.setData(_ROLE_TOPIC, topic.get("id"))
            self.topic_list.addItem(item)

        target_row = 0
        if select_id:
            for i in range(self.topic_list.count()):
                if self.topic_list.item(i).data(_ROLE_TOPIC) == select_id:
                    target_row = i
                    break
        if self.topic_list.count():
            self.topic_list.setCurrentRow(target_row)

    def _topic_by_id(self, topic_id) -> dict | None:
        for topic in HELP_TOPICS:
            if topic.get("id") == topic_id:
                return topic
        return None

    def _on_topic_changed(self, current: QListWidgetItem | None, _prev=None) -> None:
        if current is None:
            self.viewer.clear()
            return
        topic = self._topic_by_id(current.data(_ROLE_TOPIC))
        if topic is None:
            self.viewer.clear()
            return
        body = help_topic_body(topic, self._lang)
        try:
            self.viewer.setMarkdown(body)
        except Exception:
            # Fallback, falls setMarkdown nicht verfügbar ist
            self.viewer.setPlainText(body)

    def _apply_filter(self, text: str) -> None:
        needle = (text or "").strip().lower()
        first_visible = None
        visible = 0
        for i in range(self.topic_list.count()):
            item = self.topic_list.item(i)
            topic = self._topic_by_id(item.data(_ROLE_TOPIC))
            match = (not needle) or (
                topic is not None and needle in help_topic_haystack(topic, self._lang)
            )
            item.setHidden(not match)
            if match:
                visible += 1
                if first_visible is None:
                    first_visible = i
        self.empty_hint.setVisible(visible == 0)
        # Auswahl auf das erste sichtbare Thema setzen, falls die aktuelle ausgeblendet ist
        cur = self.topic_list.currentItem()
        if (cur is None or cur.isHidden()) and first_visible is not None:
            self.topic_list.setCurrentRow(first_visible)
