"""Integration test: the analysis worker on a real generated audio file.

Skips cleanly unless PySide6 + librosa + ffmpeg are all available, so it only
runs where the full audio stack is installed.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

pytest.importorskip("PySide6")
pytest.importorskip("librosa")
if shutil.which("ffmpeg") is None:
    pytest.skip("ffmpeg not on PATH", allow_module_level=True)

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.workers import AnalysisRunnable, WorkerSignals  # noqa: E402
from core import waveform  # noqa: E402


def _app():
    return QApplication.instance() or QApplication([])


def _make_beat(path: Path, seconds: int = 5) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i",
         f"sine=frequency=200:duration={seconds}", "-ac", "2", "-ar", "44100",
         "-b:a", "320k", str(path)],
        check=True, capture_output=True,
    )


def test_worker_analyzes_real_file(tmp_path):
    app = _app()
    beat = tmp_path / "beat.mp3"
    _make_beat(beat, seconds=5)
    peaks_path = tmp_path / "1.npy"

    results = {}
    errors = {}
    signals = WorkerSignals()
    signals.beat_analyzed.connect(lambda bid, res: results.update({bid: res}))
    signals.error.connect(lambda bid, msg: errors.update({bid: msg}))

    from PySide6.QtCore import QThreadPool
    pool = QThreadPool.globalInstance()
    pool.start(AnalysisRunnable(1, str(beat), str(peaks_path), signals))
    pool.waitForDone(30_000)
    for _ in range(50):
        app.processEvents()

    assert not errors, errors
    assert 1 in results
    res = results[1]
    assert res["analysis_status"] == "done"
    assert res["duration_sec"] == pytest.approx(5.0, abs=0.3)
    assert Path(res["waveform_path"]).exists()
    # Peaks are usable and normalized.
    peaks = waveform.load_peaks(res["waveform_path"])
    assert len(peaks) > 0
    assert peaks.max() <= 1.0 + 1e-6


def test_export_with_placements_real_audio(tmp_path):
    import subprocess

    from core.models import Placement, TaggingConfig
    from core import pipeline

    beat = tmp_path / "beat.mp3"
    tag = tmp_path / "tag.wav"
    _make_beat(beat, seconds=8)
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=880:duration=1",
         "-ac", "2", "-ar", "44100", str(tag)],
        check=True, capture_output=True,
    )

    out = tmp_path / "beat_tagged.mp3"
    placements = [Placement(0.0, str(tag)), Placement(4.0, str(tag))]
    result = pipeline.export_with_placements(
        str(beat), placements, str(out), TaggingConfig()
    )
    assert Path(result).exists()

    # Output duration should match the source (~8s).
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(out)],
        check=True, capture_output=True, text=True,
    )
    assert float(probe.stdout.strip()) == pytest.approx(8.0, abs=0.3)


def test_export_preview_crop_and_metadata(tmp_path):
    import subprocess

    from core.models import Placement, TaggingConfig
    from core import metadata, pipeline

    beat = tmp_path / "beat.mp3"
    tag = tmp_path / "tag.wav"
    _make_beat(beat, seconds=12)
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=880:duration=1",
         "-ac", "2", "-ar", "44100", str(tag)],
        check=True, capture_output=True,
    )

    out = tmp_path / "beat_preview.mp3"
    tags = metadata.build_id3_tags("paperhand", title="Beat", bpm=140, key="F#min")
    pipeline.export_with_placements(
        str(beat), [Placement(2.0, str(tag))], str(out), TaggingConfig(),
        crop=(2.0, 10.0), tags=tags,   # 8-second preview window
    )
    assert out.exists()

    # Cropped duration ~8s, and the producer landed in the artist tag.
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:format_tags=artist", "-of", "default=nw=1:nk=1", str(out)],
        check=True, capture_output=True, text=True,
    )
    lines = [ln for ln in probe.stdout.splitlines() if ln.strip()]
    assert float(lines[0]) == pytest.approx(8.0, abs=0.3)
    assert "paperhand" in probe.stdout


def test_tag_stem_is_beat_length_silence_plus_tags(tmp_path):
    import subprocess

    from pydub import AudioSegment

    from core.models import Placement
    from core import audio, exports

    beat = tmp_path / "beat.mp3"
    tag = tmp_path / "tag.wav"
    _make_beat(beat, seconds=8)
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=880:duration=1",
         "-ac", "2", "-ar", "44100", str(tag)],
        check=True, capture_output=True,
    )

    out = tmp_path / "stem.wav"
    exports.export_tag_stem(str(beat), [Placement(4.0, str(tag))], str(out))

    beat_seg = audio.load_audio(str(beat))
    stem = AudioSegment.from_file(str(out))
    # Same length as the beat (within a frame or two).
    assert abs(len(stem) - len(beat_seg)) < 50
    # Silent before the tag, audible at the tag.
    assert stem[0:3000].max_dBFS == float("-inf") or stem[0:3000].max_dBFS < -50
    assert stem[4000:5000].max_dBFS > -40


def test_clean_master_to_wav_converts_mp3_source(tmp_path):
    from core import exports

    src = tmp_path / "beat.mp3"
    _make_beat(src, seconds=5)
    dst = tmp_path / "masters" / "beat.wav"
    exports.export_clean_master(str(src), str(dst), to_wav=True)
    assert dst.exists()

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_name:format=duration", "-of", "default=nw=1:nk=1", str(dst)],
        check=True, capture_output=True, text=True,
    )
    assert "pcm" in probe.stdout                      # decoded to PCM WAV
    assert float(probe.stdout.splitlines()[-1]) == pytest.approx(5.0, abs=0.3)
