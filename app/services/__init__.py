"""Non-UI services: importing/scanning beats and renaming files in place.

These contain the library logic the UI calls. They touch the filesystem and the
database but never Qt, so they're testable headless.
"""
