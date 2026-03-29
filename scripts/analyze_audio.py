# scripts/analyze_audio.py

import numpy as np
import librosa
import whisper
import os
import tempfile
import subprocess

WHISPER_MODEL_NAME = os.getenv("WHISPER_MODEL", "base")
whisper_model = whisper.load_model(WHISPER_MODEL_NAME)


# -------------------------------
# Core Audio Analysis
# -------------------------------

def analyze_audio(audio_path):
    """
    Returns structured audio intelligence:
    - language
    - transcript
    - speech presence
    - loudness
    """

    if not os.path.exists(audio_path):
        return {
            "error": "Audio file not found"
        }

    # -------------------------------
    # 1. Load Audio
    # -------------------------------
    y, sr = librosa.load(audio_path, sr=16000)

    duration = librosa.get_duration(y=y, sr=sr)

    # -------------------------------
    # 2. Loudness (RMS Energy)
    # -------------------------------
    rms = librosa.feature.rms(y=y)[0]
    avg_rms = float(np.mean(rms))
    max_rms = float(np.max(rms))

    # -------------------------------
    # 3. Whisper ASR (Speech + Language)
    # -------------------------------
    transcript = ""
    language = "unknown"

    transcription_attempts = [
        {"task": "translate", "fp16": False, "beam_size": 1, "best_of": 1, "condition_on_previous_text": False},
        {"task": "transcribe", "fp16": False, "beam_size": 1, "best_of": 1, "condition_on_previous_text": False},
    ]

    for attempt in transcription_attempts:
        try:
            result = whisper_model.transcribe(audio_path, **attempt)
            transcript = result.get("text", "").strip()
            language = result.get("language", "unknown")
            if transcript:
                break
        except Exception as e:
            print(f"[Audio] Whisper failed ({attempt['task']}): {e}")

    if not transcript and duration > 0:
        clipped_audio_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                clipped_audio_path = temp_file.name

            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i", audio_path,
                    "-t", "180",
                    "-ac", "1",
                    "-ar", "16000",
                    clipped_audio_path,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )

            result = whisper_model.transcribe(
                clipped_audio_path,
                task="translate",
                fp16=False,
                beam_size=1,
                best_of=1,
                condition_on_previous_text=False,
            )
            transcript = result.get("text", "").strip()
            language = result.get("language", "unknown")
        except Exception as e:
            print(f"[Audio] Whisper clipped retry failed: {e}")
        finally:
            if clipped_audio_path and os.path.exists(clipped_audio_path):
                os.remove(clipped_audio_path)

    # -------------------------------
    # 4. Speech Presence Detection (Better Logic)
    # -------------------------------
    speaking = len(transcript) > 10  # if meaningful speech exists

    # -------------------------------
    # 5. Shouting / Intensity Estimation
    # -------------------------------
    # More stable than fixed threshold
    if avg_rms > 0.18 or max_rms > 0.4:
        intensity = "high"
    elif avg_rms > 0.06:
        intensity = "moderate"
    else:
        intensity = "low"

    # -------------------------------
    # 6. Final Structured Output
    # -------------------------------

    return {
        "duration_sec": round(duration, 2),

        "language": language,
        "transcript": transcript,

        "speaking": speaking,
        "intensity": intensity,

        "avg_rms": round(avg_rms, 4),
        "max_rms": round(max_rms, 4)
    }


# -------------------------------
# Backward Compatibility Wrapper
# -------------------------------

def analyze_audio_legacy(audio_path):
    """
    Keeps compatibility with old pipeline
    """

    result = analyze_audio(audio_path)

    return {
        "speaking": result.get("speaking", False),
        "shouting": result.get("intensity") == "high",
        "avg_rms": result.get("avg_rms", 0)
    }


# -------------------------------
# Debug Run
# -------------------------------

if __name__ == "__main__":
    AUDIO_PATH = "data/processed_videos/LuZV9kkzscg/audio.wav"

    output = analyze_audio(AUDIO_PATH)

    print("\n--- FULL AUDIO OUTPUT ---")
    print(output)

    print("\n--- LEGACY OUTPUT ---")
    print(analyze_audio_legacy(AUDIO_PATH))
