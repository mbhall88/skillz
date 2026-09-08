# Locked ML API evidence

Inspected on 2026-09-08, without loading models or processing audio:
WhisperX 3.8.6, pyannote.audio 4.0.7, torch/torchaudio 2.8.0.
The dependency lock is unchanged.

- Installed `pyannote/audio/core/inference.py:78` accepts `model: Model`
  and has no `use_auth_token` argument. `core/model.py:498` exposes
  `Model.from_pretrained(..., token=...)`. The embedding adapter now loads
  `pyannote/embedding` with that method and calls `Inference(model, window="whole")`.
- Installed `whisperx/diarize.py:92` accepts `model_name` and `token`.
  Its default is community-1. We explicitly pass
  `pyannote/speaker-diarization-3.1` to keep the approved model.
- Installed `pyannote/audio/core/pipeline.py:260` converts older `version`
  configs to dependency metadata before constructing the configured pipeline.
  `pipelines/speaker_diarization.py:195` defaults `legacy=False` and supports
  `AgglomerativeClustering`, used by 3.1. Its default return has
  `speaker_diarization`, which the WhisperX 3.8.6 wrapper reads at line 167.
  This is source-level compatibility evidence, not an executed model test.
- In pyannote.audio 4.0.7, the `SpeakerDiarization` constructor also loads
  community-1 PLDA assets unconditionally, although 3.1's agglomerative
  clustering does not use them. This is visible in the installed constructor
  and reported in [upstream issue 2044](https://github.com/pyannote/pyannote-audio/issues/2044).
  Setup therefore documents the additional community-1 access requirement;
  it does not change the selected diarization model. The issue also identifies
  the 3.1 configuration's gated segmentation-3.0 dependency.
- Installed `whisperx/audio.py:14` defines a 16,000 Hz sample rate, used by
  `load_audio`. Duration is waveform length divided by 16,000, including
  trailing silence. No duration is inferred from the last aligned word.

Offline contract tests replace the external model classes and check the
constructor arguments and separate crop spans. Gated downloads, checkpoint
deserialization, real inference, and match-threshold calibration have not
been verified in this fix wave, as requested.

## Findings from the first live end-to-end run (2026-09-08)

A real 24-minute `.m4a` recording surfaced two defects the offline contract
tests could not catch, since both only manifest with real model execution:

- **Language auto-detection is unreliable.** WhisperX detects language from
  only the first 30s of audio; on this recording it picked Norwegian
  Nynorsk (`nn`, 0.74 confidence) for what is entirely English speech,
  producing a fully garbled transcript (e.g. "Hei, Michael. Hvordan går
  det?" for "Hi, Michael. How are you?") with near-zero alignment
  confidence scores throughout. Fixed by forcing `language=` on
  `model.transcribe()` via a new `config.get_language()` (default `"en"`,
  overridable with `MEETING_LANGUAGE`) rather than relying on auto-detect.
- **Embedding extraction fails for every speaker in this environment.**
  `Inference.crop()` on a bare file path requires torchcodec, which fails
  to load here (`Library not loaded: @rpath/libavutil.*.dylib` — the
  installed `torchcodec` build doesn't match the installed ffmpeg dylibs).
  Every speaker's `centroid_for_segments` call raised
  `RuntimeError: torchcodec is not available...`, so no voiceprint could
  be computed at all — the enrollment/matching feature was completely
  non-functional. Per `pyannote/audio/core/io.py`'s own `Audio.crop`, a
  preloaded `{"waveform": tensor, "sample_rate": int}` dict skips the
  torchcodec path entirely. Fixed in `embedding_extraction.py` by loading
  the wav once via `torchaudio.load()` (cached per audio path) and passing
  that dict to `inference.crop()` instead of the file path.
