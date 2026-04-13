"""SpeexDSP noise suppression wrapper via ctypes.
No compilation needed — uses the system libspeexdsp.so directly.
Designed for car environment: engine noise, road noise, wind.
"""

import ctypes
import ctypes.util
import struct

# Load system library
_lib_path = ctypes.util.find_library("speexdsp")
if not _lib_path:
    _lib_path = "/usr/lib/arm-linux-gnueabihf/libspeexdsp.so"
_lib = ctypes.CDLL(_lib_path)

# SpeexDSP preprocessor constants
SPEEX_PREPROCESS_SET_DENOISE = 0
SPEEX_PREPROCESS_SET_AGC = 2
SPEEX_PREPROCESS_SET_AGC_LEVEL = 24
SPEEX_PREPROCESS_SET_NOISE_SUPPRESS = 8
SPEEX_PREPROCESS_SET_AGC_MAX_GAIN = 30
SPEEX_PREPROCESS_SET_DEREVERB = 10

# Function signatures
_lib.speex_preprocess_state_init.restype = ctypes.c_void_p
_lib.speex_preprocess_state_init.argtypes = [ctypes.c_int, ctypes.c_int]
_lib.speex_preprocess_state_destroy.argtypes = [ctypes.c_void_p]
_lib.speex_preprocess_run.restype = ctypes.c_int
_lib.speex_preprocess_run.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_short)]
_lib.speex_preprocess_ctl.restype = ctypes.c_int
_lib.speex_preprocess_ctl.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]


class NoiseSuppressor:
    """Real-time noise suppression optimized for car environments.

    Uses SpeexDSP preprocessor with:
    - Noise suppression (removes steady-state noise like engine/road)
    - Auto Gain Control (normalizes mic volume for near/far speakers)
    - Dereverb (reduces echo from car cabin)
    """

    def __init__(self, frame_size=160, sample_rate=16000,
                 noise_suppress_db=-30, agc_level=24000):
        """
        Args:
            frame_size: samples per frame (160 = 10ms at 16kHz)
            sample_rate: audio sample rate
            noise_suppress_db: noise reduction strength (-15 to -45, more negative = stronger)
            agc_level: target output level for AGC (8000-32000)
        """
        self.frame_size = frame_size
        self.state = _lib.speex_preprocess_state_init(frame_size, sample_rate)

        # Enable noise suppression
        val = ctypes.c_int(1)
        _lib.speex_preprocess_ctl(self.state, SPEEX_PREPROCESS_SET_DENOISE,
                                  ctypes.byref(val))

        # Set noise suppression level
        ns_level = ctypes.c_int(noise_suppress_db)
        _lib.speex_preprocess_ctl(self.state, SPEEX_PREPROCESS_SET_NOISE_SUPPRESS,
                                  ctypes.byref(ns_level))

        # Enable AGC (auto gain control) — crucial for car use
        agc = ctypes.c_int(1)
        _lib.speex_preprocess_ctl(self.state, SPEEX_PREPROCESS_SET_AGC,
                                  ctypes.byref(agc))

        # Set AGC target level
        agc_lvl = ctypes.c_int(agc_level)
        _lib.speex_preprocess_ctl(self.state, SPEEX_PREPROCESS_SET_AGC_LEVEL,
                                  ctypes.byref(agc_lvl))

        # Set max AGC gain (important for far speakers in car)
        max_gain = ctypes.c_int(40)  # up to 40dB gain
        _lib.speex_preprocess_ctl(self.state, SPEEX_PREPROCESS_SET_AGC_MAX_GAIN,
                                  ctypes.byref(max_gain))

        # Enable dereverb (car cabin echo)
        derev = ctypes.c_int(1)
        _lib.speex_preprocess_ctl(self.state, SPEEX_PREPROCESS_SET_DEREVERB,
                                  ctypes.byref(derev))

    def process(self, audio_bytes):
        """Process a frame of S16_LE mono audio, return denoised bytes.

        Args:
            audio_bytes: bytes of S16_LE mono audio (frame_size * 2 bytes)
        Returns:
            Denoised audio bytes, same format
        """
        n_samples = len(audio_bytes) // 2
        # Process in frame_size chunks
        output = bytearray()
        for offset in range(0, n_samples, self.frame_size):
            chunk_bytes = audio_bytes[offset*2 : (offset + self.frame_size)*2]
            if len(chunk_bytes) < self.frame_size * 2:
                output.extend(chunk_bytes)
                break

            frame = (ctypes.c_short * self.frame_size)()
            for i in range(self.frame_size):
                frame[i] = struct.unpack_from("<h", chunk_bytes, i * 2)[0]

            _lib.speex_preprocess_run(self.state, frame)

            for i in range(self.frame_size):
                output.extend(struct.pack("<h", frame[i]))

        return bytes(output)

    def destroy(self):
        if self.state:
            _lib.speex_preprocess_state_destroy(self.state)
            self.state = None

    def __del__(self):
        self.destroy()
