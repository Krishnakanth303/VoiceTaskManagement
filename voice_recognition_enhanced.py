"""
Enhanced Voice Recognition Module for Blind Assistance App
===========================================================
Fixes:
  1. Works in noisy environments using spectral noise reduction
  2. Speaker voice enrollment - learns the user's voice profile
  3. Dynamic VAD (Voice Activity Detection) - stops recording when user stops speaking
  4. Adaptive energy threshold - calibrates to ambient noise automatically
  5. Speaker verification - only accepts input from the registered user

Dependencies (add to requirements.txt):
    noisereduce==3.0.2
    webrtcvad==2.0.10
    librosa==0.10.1
"""

import os
import json
import wave
import time
import pickle
import threading
import numpy as np
import sounddevice as sd
import speech_recognition as sr
from pathlib import Path

# ── Optional imports with graceful fallback ──────────────────────────────────
try:
    import noisereduce as nr
    NOISEREDUCE_AVAILABLE = True
except ImportError:
    NOISEREDUCE_AVAILABLE = False
    print("[VoiceEngine] noisereduce not installed. Run: pip install noisereduce")

try:
    import webrtcvad
    WEBRTCVAD_AVAILABLE = True
except ImportError:
    WEBRTCVAD_AVAILABLE = False
    print("[VoiceEngine] webrtcvad not installed. Run: pip install webrtcvad")

try:
    import librosa
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False
    print("[VoiceEngine] librosa not installed. Run: pip install librosa")

# ── Constants ────────────────────────────────────────────────────────────────
SAMPLE_RATE        = 16000          # 16 kHz — optimal for speech recognition
CHANNELS           = 1              # Mono
FRAME_DURATION_MS  = 30             # WebRTC VAD frame size (10 / 20 / 30 ms)
BYTES_PER_SAMPLE   = 2
FRAME_SIZE         = int(SAMPLE_RATE * FRAME_DURATION_MS / 1000)  # samples per frame

NOISE_PROFILE_DIR  = "voice_profiles"
WORD_PAUSE_FRAMES  = 67             # ~2 seconds silence allowed between words (2000ms / 30ms)
MIN_STOP_FRAMES    = 100            # ~3 seconds silence to stop recording
MIN_SPEECH_FRAMES  = 5              # need at least 5 frames to confirm speech
MAX_RECORD_SECONDS = 15             # hard ceiling
SPEAKER_PROFILE_FILE = os.path.join(NOISE_PROFILE_DIR, "speaker_profiles.pkl")

os.makedirs(NOISE_PROFILE_DIR, exist_ok=True)


# ────────────────────────────────────────────────────────────────────────────
# 1. NOISE CAPTURE  –  record ~1 s of ambient noise for the profile
# ────────────────────────────────────────────────────────────────────────────
def capture_noise_profile(duration: float = 1.5) -> np.ndarray:
    """Record ambient noise so we can subtract it later."""
    print(f"[VoiceEngine] Capturing {duration}s noise profile …")
    audio = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=np.int16,
    )
    sd.wait()
    return audio.flatten().astype(np.float32)


# ────────────────────────────────────────────────────────────────────────────
# 2. NOISE REDUCTION  –  spectral subtraction via noisereduce
# ────────────────────────────────────────────────────────────────────────────
def reduce_noise(audio_int16: np.ndarray, noise_profile: np.ndarray | None = None) -> np.ndarray:
    """
    Apply spectral noise reduction.
    audio_int16  : int16 numpy array (raw PCM)
    noise_profile: float32 numpy array of ambient noise (captured above)
    Returns      : cleaned int16 array
    """
    if not NOISEREDUCE_AVAILABLE:
        return audio_int16  # pass-through if library missing

    audio_f32 = audio_int16.astype(np.float32) / 32768.0

    if noise_profile is not None:
        noise_f32 = noise_profile / (np.max(np.abs(noise_profile)) + 1e-8)
        # Lower prop_decrease to preserve more speech details in noisy environments
        cleaned = nr.reduce_noise(
            y=audio_f32,
            sr=SAMPLE_RATE,
            y_noise=noise_f32,
            prop_decrease=0.65,      # reduced from 0.85 for better speech preservation
            stationary=False,        # handles dynamic noise (fan, crowd, AC)
        )
    else:
        # Stationary noise estimation from the signal itself
        # Use lower prop_decrease for better speech clarity
        cleaned = nr.reduce_noise(
            y=audio_f32,
            sr=SAMPLE_RATE,
            stationary=True,
            prop_decrease=0.55,      # reduced from 0.75 for better speech preservation
        )

    return (cleaned * 32768.0).astype(np.int16)


# ────────────────────────────────────────────────────────────────────────────
# 3. VOICE ACTIVITY DETECTION  –  stop recording when user stops speaking
# ────────────────────────────────────────────────────────────────────────────
def record_with_vad(max_seconds: int = MAX_RECORD_SECONDS) -> np.ndarray:
    """
    Record audio, stopping automatically after 3 seconds of silence.
    Allows 2-second pauses between words.
    Uses WebRTC VAD when available, falls back to energy-based VAD.
    Returns int16 numpy array.
    """
    frames_recorded: list[np.ndarray] = []
    silence_count = 0
    speaking_started = False
    voice_frame_count = 0  # track continuous speech frames
    consecutive_silence = 0  # track total silence since speech started

    if WEBRTCVAD_AVAILABLE:
        vad = webrtcvad.Vad(1)   # aggressiveness 1 = least aggressive (better for capturing quiet speech)

    print("[VoiceEngine] Listening… (allows 2s pauses between words, stops after 3s silence)")

    # Stream audio in small frames
    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16",
        blocksize=FRAME_SIZE,
    ) as stream:
        deadline = time.time() + max_seconds
        while time.time() < deadline:
            frame, _ = stream.read(FRAME_SIZE)
            pcm = frame.flatten()
            frames_recorded.append(pcm)

            # Determine if this frame contains speech
            if WEBRTCVAD_AVAILABLE:
                try:
                    is_speech = vad.is_speech(pcm.tobytes(), SAMPLE_RATE)
                except Exception:
                    is_speech = _energy_vad(pcm)
            else:
                is_speech = _energy_vad(pcm)

            if is_speech:
                speaking_started = True
                silence_count = 0  # reset short pause counter
                consecutive_silence = 0  # reset total silence counter
                voice_frame_count += 1
            elif speaking_started:
                silence_count += 1
                consecutive_silence += 1
                
                # Stop only if 3+ seconds of silence AND we've already heard speech
                if consecutive_silence >= MIN_STOP_FRAMES and voice_frame_count >= MIN_SPEECH_FRAMES:
                    print(f"[VoiceEngine] 3-second silence detected – stopping recording.")
                    break
                # For logging: show when 2-second pause happens (normal between words)
                elif silence_count == WORD_PAUSE_FRAMES and voice_frame_count >= MIN_SPEECH_FRAMES:
                    print(f"[VoiceEngine] Detected 2s pause (allows continuing if speech resumes)…")

    audio = np.concatenate(frames_recorded, axis=0).astype(np.int16)
    print(f"[VoiceEngine] Recorded {len(audio) / SAMPLE_RATE:.1f}s of audio.")
    return audio


def _energy_vad(frame: np.ndarray, threshold: float = 50.0) -> bool:
    """Simple RMS energy threshold as fallback VAD (very low threshold to catch quiet speech)."""
    rms = np.sqrt(np.mean(frame.astype(np.float32) ** 2))
    # Also check for any sound activity above near-silence
    is_active = rms > threshold or rms > 30  # fallback to very low threshold
    return is_active


# ────────────────────────────────────────────────────────────────────────────
# 4. SPEAKER PROFILE  –  MFCC-based voice fingerprint
# ────────────────────────────────────────────────────────────────────────────
class SpeakerProfile:
    """
    Stores a voice fingerprint (mean MFCC vector) for each enrolled user.
    Used to verify that the person speaking is the registered user.
    """

    def __init__(self):
        self.profiles: dict[str, np.ndarray] = {}
        self._load()

    def _load(self):
        if os.path.exists(SPEAKER_PROFILE_FILE):
            try:
                with open(SPEAKER_PROFILE_FILE, "rb") as f:
                    self.profiles = pickle.load(f)
                print(f"[VoiceEngine] Loaded {len(self.profiles)} speaker profile(s).")
            except Exception as e:
                print(f"[VoiceEngine] Could not load profiles: {e}")

    def _save(self):
        with open(SPEAKER_PROFILE_FILE, "wb") as f:
            pickle.dump(self.profiles, f)

    def enroll(self, name: str, audio_int16: np.ndarray):
        """
        Enroll (or update) a speaker by computing their mean MFCC fingerprint.
        Call this with several seconds of the user's clear speech.
        """
        if not LIBROSA_AVAILABLE:
            print("[VoiceEngine] librosa not available – speaker enrollment skipped.")
            return
        audio_f32 = audio_int16.astype(np.float32) / 32768.0
        mfcc = librosa.feature.mfcc(y=audio_f32, sr=SAMPLE_RATE, n_mfcc=40)
        fingerprint = mfcc.mean(axis=1)  # shape (40,)
        # Running average if user re-enrolls
        if name in self.profiles:
            self.profiles[name] = 0.6 * self.profiles[name] + 0.4 * fingerprint
        else:
            self.profiles[name] = fingerprint
        self._save()
        print(f"[VoiceEngine] Speaker '{name}' enrolled/updated.")

    def verify(self, name: str, audio_int16: np.ndarray, threshold: float = 25.0) -> bool:
        """
        Returns True if the audio sounds like `name`.
        `threshold` is cosine distance (lower = stricter). 25.0 is lenient.
        """
        if not LIBROSA_AVAILABLE or name not in self.profiles:
            return True   # allow through if we can't verify

        audio_f32 = audio_int16.astype(np.float32) / 32768.0
        mfcc = librosa.feature.mfcc(y=audio_f32, sr=SAMPLE_RATE, n_mfcc=40)
        current = mfcc.mean(axis=1)
        stored  = self.profiles[name]

        # Cosine distance
        dot = np.dot(current, stored)
        norm = np.linalg.norm(current) * np.linalg.norm(stored) + 1e-8
        cosine_sim = dot / norm
        distance = (1 - cosine_sim) * 100

        print(f"[VoiceEngine] Speaker distance for '{name}': {distance:.2f} (threshold {threshold})")
        return distance < threshold

    def has_profile(self, name: str) -> bool:
        return name in self.profiles


# ── Singleton profile store ──────────────────────────────────────────────────
_speaker_profile = SpeakerProfile()


# ────────────────────────────────────────────────────────────────────────────
# 5. SAVE AUDIO TO WAV
# ────────────────────────────────────────────────────────────────────────────
def save_wav(audio_int16: np.ndarray, filename: str = "input_audio.wav"):
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(BYTES_PER_SAMPLE)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio_int16.tobytes())


# ────────────────────────────────────────────────────────────────────────────
# 6. TRANSCRIPTION  –  Google STT with noise-cleaned audio
# ────────────────────────────────────────────────────────────────────────────
def transcribe(audio_int16: np.ndarray, filename: str = "input_audio.wav") -> str | None:
    """Send cleaned audio to Google Speech-to-Text."""
    save_wav(audio_int16, filename)
    recognizer = sr.Recognizer()
    # Ultra-sensitive settings for noisy environments
    recognizer.energy_threshold = 50         # very low to catch quiet speech
    recognizer.dynamic_energy_threshold = True
    recognizer.dynamic_energy_adjustment_damping = 0.02  # very responsive
    recognizer.dynamic_energy_ratio = 1.1    # lenient ratio

    with sr.AudioFile(filename) as source:
        # Longer and more aggressive ambient noise adjustment
        recognizer.adjust_for_ambient_noise(source, duration=1.0)  # increased from 0.5 for better adaptation
        audio_data = recognizer.record(source)

    try:
        text = recognizer.recognize_google(audio_data, language="en-US")
        return text.lower().strip()
    except sr.UnknownValueError:
        print("[VoiceEngine] STT could not understand audio.")
        return None
    except sr.RequestError as e:
        print(f"[VoiceEngine] STT request error: {e}")
        return None


# ────────────────────────────────────────────────────────────────────────────
# 7. MAIN PUBLIC API
# ────────────────────────────────────────────────────────────────────────────

# Module-level noise profile (captured once at startup)
_ambient_noise: np.ndarray | None = None
_noise_lock = threading.Lock()


def calibrate_noise():
    """Call once at app startup to capture the ambient noise profile."""
    global _ambient_noise
    with _noise_lock:
        _ambient_noise = capture_noise_profile(duration=2.0)  # longer sampling for better noise model
    print("[VoiceEngine] Ambient noise calibrated.")


def enroll_speaker(name: str, tts_fn=None) -> bool:
    """
    Enroll a new user's voice. Records ~5 s of their speech.
    `tts_fn` is optional callback to speak instructions aloud.
    Returns True on success.
    """
    global _ambient_noise
    if tts_fn:
        tts_fn(f"Hi {name}, please say a few sentences so I can learn your voice. Start speaking when ready.")
    else:
        print(f"Please say a few sentences so the app can learn your voice.")

    # Capture noise first
    _ambient_noise = capture_noise_profile(1.0)

    audio = record_with_vad(max_seconds=8)

    if len(audio) < SAMPLE_RATE:   # less than 1 second – too short
        print("[VoiceEngine] Enrollment audio too short.")
        return False

    cleaned = reduce_noise(audio, _ambient_noise)
    _speaker_profile.enroll(name, cleaned)

    if tts_fn:
        tts_fn("Voice enrolled successfully.")
    return True


def voice_to_text_enhanced(
    prompt: str,
    tts_fn=None,
    username: str | None = None,
    max_retries: int = 4,
    verify_speaker: bool = True,
) -> str:
    """
    Drop-in replacement for the original voice_to_text().

    Parameters
    ----------
    prompt        : What to say before listening (e.g. "say your name")
    tts_fn        : Callable(str) that speaks text aloud
    username      : Logged-in user's name for speaker verification
    max_retries   : How many times to retry on failure
    verify_speaker: Whether to enforce that the voice matches `username`

    Returns       : Recognised text (lowercased), or "" on total failure
    """
    global _ambient_noise

    for attempt in range(1, max_retries + 1):
        print(f"[VoiceEngine] Attempt {attempt}/{max_retries} – prompt: '{prompt}'")

        # 1. Speak the prompt
        if tts_fn:
            tts_fn(prompt)

        # 2. Briefly re-sample ambient noise each attempt (handles changing environments)
        with _noise_lock:
            _ambient_noise = capture_noise_profile(1.0)  # increased from 0.8 for better noise profiling

        # 3. Record with VAD
        raw_audio = record_with_vad(max_seconds=MAX_RECORD_SECONDS)

        if len(raw_audio) < int(SAMPLE_RATE * 0.5):
            print("[VoiceEngine] Recording too short, retrying …")
            continue

        # 4. Speaker verification (if enrolled and requested)
        if verify_speaker and username and _speaker_profile.has_profile(username):
            cleaned_for_verify = reduce_noise(raw_audio, _ambient_noise)
            if not _speaker_profile.verify(username, cleaned_for_verify):
                print(f"[VoiceEngine] Voice does not match '{username}', retrying …")
                if tts_fn:
                    tts_fn("I did not recognise your voice. Please try again.")
                continue

        # 5. Noise reduction on the captured audio
        cleaned_audio = reduce_noise(raw_audio, _ambient_noise)

        # 6. Transcribe
        text = transcribe(cleaned_audio)

        if text:
            print(f"[VoiceEngine] Recognised: '{text}'")
            return text
        else:
            if tts_fn:
                tts_fn("Sorry, I did not catch that. Please say it again.")

    print("[VoiceEngine] All retries exhausted.")
    if tts_fn:
        tts_fn("I was unable to understand you. Please try again later.")
    return ""


# ────────────────────────────────────────────────────────────────────────────
# 8. UTILITY – check which optional packages are available
# ────────────────────────────────────────────────────────────────────────────
def print_capability_report():
    print("\n=== Voice Engine Capability Report ===")
    print(f"  noisereduce  (spectral noise gate) : {'✓ available' if NOISEREDUCE_AVAILABLE else '✗ missing  → pip install noisereduce'}")
    print(f"  webrtcvad    (VAD stop-on-silence)  : {'✓ available' if WEBRTCVAD_AVAILABLE  else '✗ missing  → pip install webrtcvad'}")
    print(f"  librosa      (speaker fingerprint)  : {'✓ available' if LIBROSA_AVAILABLE     else '✗ missing  → pip install librosa'}")
    print("=======================================\n")
