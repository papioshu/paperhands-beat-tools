"""A titled section with a corner button to collapse/expand its content.

Lets the user hide panels they aren't using (more room for the rest) while the
splitters still allow resizing. Collapsed, only the header bar remains.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget


class CollapsibleSection(QWidget):
    def __init__(self, title: str, content: QWidget, collapsed: bool = False):
        super().__init__()
        self.content = content

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2)

        header = QHBoxLayout()
        header.setContentsMargins(8, 2, 4, 0)
        self.title = QLabel(title)
        self.title.setObjectName("Heading")
        self.toggle = QToolButton()
        self.toggle.setAutoRaise(True)
        self.toggle.setCheckable(True)
        self.toggle.setCursor(Qt.PointingHandCursor)
        self.toggle.setToolTip("Collapse / expand")
        header.addWidget(self.title)
        header.addStretch(1)
        header.addWidget(self.toggle)
        outer.addLayout(header)
        outer.addWidget(content)

        self.toggle.toggled.connect(self._apply)
        self.toggle.setChecked(collapsed)
        self._apply(collapsed)

    def _apply(self, collapsed: bool) -> None:
        self.content.setVisible(not collapsed)
        self.toggle.setText("▸" if collapsed else "▾")
