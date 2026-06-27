"""The app's colour palette and Qt stylesheet.

Single source of truth for the **violet / lime / gunmetal grey** look. The
stylesheet is generated from ``COLORS`` so widgets and QSS never drift apart.
"""

from __future__ import annotations

# Core palette ---------------------------------------------------------------
COLORS = {
    # Gunmetal greys (backgrounds, deepest -> lightest surface)
    "bg":          "#1E2127",  # window background
    "panel":       "#262A32",  # cards / panels
    "surface":     "#2F343D",  # inputs, rows
    "surface_alt": "#363B45",  # hover / alternating rows
    "border":      "#3D434F",

    # Violet (primary accent)
    "violet":      "#8B5CF6",
    "violet_dim":  "#6D44D9",
    "violet_deep": "#3A2D63",  # selection wash

    # Lime (secondary accent / highlights, e.g. playhead, "analyzed" state)
    "lime":        "#B6F500",
    "lime_dim":    "#8FBF00",

    # Text
    "text":        "#E6E8EB",
    "text_dim":    "#9AA0AB",
    "text_faint":  "#6B7280",

    # Status
    "error":       "#FF6B6B",
    "warn":        "#FFB454",

    # Row states (library list)
    "edited":      "#2E7D46",  # green wash: item has unsaved edits
}


def build_stylesheet() -> str:
    c = COLORS
    return f"""
    QWidget {{
        background-color: {c['bg']};
        color: {c['text']};
        font-family: "Segoe UI", "Inter", sans-serif;
        font-size: 13px;
    }}
    QMainWindow, QDialog {{ background-color: {c['bg']}; }}

    /* Panels / frames */
    QFrame#Panel, QGroupBox {{
        background-color: {c['panel']};
        border: 1px solid {c['border']};
        border-radius: 8px;
    }}
    QGroupBox {{ margin-top: 10px; padding: 10px; }}
    QGroupBox::title {{
        subcontrol-origin: margin; left: 10px; padding: 0 4px;
        color: {c['text_dim']};
    }}

    /* Labels */
    QLabel#Heading {{ font-size: 18px; font-weight: 600; }}
    QLabel#SubHeading {{ color: {c['text_dim']}; }}
    QLabel#AccentLime {{ color: {c['lime']}; font-weight: 600; }}

    /* Inputs */
    QLineEdit, QComboBox, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox {{
        background-color: {c['surface']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        padding: 5px 8px;
        selection-background-color: {c['violet']};
    }}
    QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus, QTextEdit:focus {{
        border: 1px solid {c['violet']};
    }}

    /* Buttons */
    QPushButton {{
        background-color: {c['surface']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        padding: 6px 14px;
    }}
    QPushButton:hover {{ background-color: {c['surface_alt']}; }}
    QPushButton:pressed {{ background-color: {c['violet_deep']}; }}
    QPushButton#Primary {{
        background-color: {c['violet']};
        border: 1px solid {c['violet']};
        color: white;
        font-weight: 600;
    }}
    QPushButton#Primary:hover {{ background-color: {c['violet_dim']}; }}
    QPushButton#Accent {{
        background-color: {c['lime']};
        border: 1px solid {c['lime']};
        color: #1A1A1A;
        font-weight: 700;
    }}
    QPushButton#Accent:hover {{ background-color: {c['lime_dim']}; }}
    QPushButton:disabled {{ color: {c['text_faint']}; border-color: {c['border']}; }}

    /* Tables / lists */
    QTableView, QTableWidget, QListView, QListWidget, QTreeView {{
        background-color: {c['panel']};
        alternate-background-color: {c['surface']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        gridline-color: {c['border']};
        selection-background-color: {c['violet']};
        selection-color: white;
    }}
    QHeaderView::section {{
        background-color: {c['surface']};
        color: {c['text_dim']};
        border: none;
        border-bottom: 1px solid {c['border']};
        padding: 6px 8px;
        font-weight: 600;
    }}
    /* Selected rows read clearly purple, overriding any row background (e.g. edited-green). */
    QTableView::item:selected, QTableWidget::item:selected {{
        background-color: {c['violet']}; color: white;
    }}

    /* Splitter */
    QSplitter::handle {{ background-color: {c['border']}; }}
    QSplitter::handle:horizontal {{ width: 3px; }}
    QSplitter::handle:vertical {{ height: 3px; }}

    /* Scrollbars */
    QScrollBar:vertical {{ background: {c['bg']}; width: 12px; margin: 0; }}
    QScrollBar::handle:vertical {{
        background: {c['surface_alt']}; border-radius: 6px; min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {c['violet_dim']}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}

    /* Toolbar / status bar / menu */
    QToolBar {{ background-color: {c['panel']}; border: none; spacing: 6px; padding: 6px; }}
    QStatusBar {{ background-color: {c['panel']}; color: {c['text_dim']}; }}
    QMenuBar {{ background-color: {c['panel']}; }}
    QMenuBar::item:selected {{ background-color: {c['violet_deep']}; }}
    QMenu {{ background-color: {c['panel']}; border: 1px solid {c['border']}; }}
    QMenu::item:selected {{ background-color: {c['violet_deep']}; }}

    /* Sliders (transport) */
    QSlider::groove:horizontal {{ height: 4px; background: {c['surface']}; border-radius: 2px; }}
    QSlider::sub-page:horizontal {{ background: {c['violet']}; border-radius: 2px; }}
    QSlider::handle:horizontal {{
        background: {c['lime']}; width: 12px; margin: -5px 0; border-radius: 6px;
    }}
    """


def apply_theme(app) -> None:
    """Apply the palette + stylesheet to a QApplication."""
    from PySide6.QtGui import QColor, QPalette

    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(COLORS["bg"]))
    pal.setColor(QPalette.Base, QColor(COLORS["panel"]))
    pal.setColor(QPalette.AlternateBase, QColor(COLORS["surface"]))
    pal.setColor(QPalette.Text, QColor(COLORS["text"]))
    pal.setColor(QPalette.WindowText, QColor(COLORS["text"]))
    pal.setColor(QPalette.Button, QColor(COLORS["surface"]))
    pal.setColor(QPalette.ButtonText, QColor(COLORS["text"]))
    pal.setColor(QPalette.Highlight, QColor(COLORS["violet"]))
    pal.setColor(QPalette.HighlightedText, QColor(COLORS["text"]))
    app.setPalette(pal)
    app.setStyleSheet(build_stylesheet())
