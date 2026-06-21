"""Paperhand's Beat Tools — shared audio engine.

Kept import-light on purpose: importing ``core`` (or the pure-logic modules
``core.naming`` / ``core.placement`` / ``core.models``) must NOT require ffmpeg,
pydub, or librosa. The heavy audio libraries are imported lazily inside
``core.audio`` / ``core.detection`` so unit tests and the GUI can use the pure
logic without the audio stack installed.
"""
