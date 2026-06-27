"""Single source of truth for the app version (compared against GitHub releases)."""

__version__ = "1.2.0"

# Default GitHub repo the app checks for updates ("owner/name"). Overridable in
# Settings -> Updates. Public, so release checks work anonymously.
UPDATE_REPO = "papioshu/paperhands-beat-tools"
