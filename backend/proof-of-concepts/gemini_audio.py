import asyncio
import sys
import traceback
import numpy as np
from collections import deque
from scipy import signal
from scipy.signal import butter, filtfilt, welch
import threading
import time

import pyaudio
import os
from dotenv import load_dotenv
load_dotenv()
from google import genai
from google.genai import types
from tools import get_tool
from prompts import get_prompt, get_tool_config

if sys.version_info < (3, 11, 0):
    import taskgroup, exceptiongroup  # noqa: E401

    asyncio.TaskGroup = taskgroup.TaskGroup
    asyncio.ExceptionGroup = exceptiongroup.ExceptionGroup

FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024

# MODEL = "gemini-2.5-flash-preview-native-audio-dialog"
# MODEL = "gemini-2.0-flash-exp"
MODEL = "gemini-2.0-flash-live-001"
API_KEY = os.getenv("API_KEY")
ASSISTANT_NAME = "yoda_diagnostics"
SYSTEM_PROMPT = get_prompt(ASSISTANT_NAME)
TOOL_CONFIG = get_tool_config(ASSISTANT_NAME)

pya = pyaudio.PyAudio()


client = genai.Client(
    api_key=API_KEY,
    http_options={"api_version": "v1beta"},
)


CONFIG = types.LiveConnectConfig(
    response_modalities=[
        "AUDIO",
    ],
    # speech_config=types.SpeechConfig(
    #     voice_config=types.VoiceConfig(
    #         prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Sulafat")
    #     )
    # ),
    context_window_compression=types.ContextWindowCompressionConfig(
        trigger_tokens=25600,
        sliding_window=types.SlidingWindow(target_tokens=12800),
    ),
    realtime_input_config=types.RealtimeInputConfig(
        turn_coverage="TURN_INCLUDES_ALL_INPUT"
    ),
    system_instruction=SYSTEM_PROMPT,
    tools=[TOOL_CONFIG],
)

class AudioFilter:
    """Advanced audio filtering with echo cancellation, noise suppression, and VAD"""
    
    def __init__(self, sample_rate=16000, chunk_size=1024):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        
        # Filter parameters
        self.vad_threshold = -30  # dB
        self.noise_gate_threshold = -40  # dB
        self.echo_suppression_level = 0.8
        self.noise_floor = -60  # dB
        
        # Audio buffers for processing
        self.audio_buffer = deque(maxlen=int(sample_rate * 2))  # 2 second buffer
        self.agent_audio_buffer = deque(maxlen=int(sample_rate * 1))  # 1 second for echo reference
        self.noise_profile = None
        
        # State tracking
        self.agent_speaking = False
        self.voice_active = False
        self.silence_counter = 0
        self.silence_threshold = 30  # chunks of silence before considering inactive
        
        # Adaptive filters
        self.adaptive_filter_length = 256
        self.adaptive_filter_weights = np.zeros(self.adaptive_filter_length)
        self.mu = 0.01  # LMS adaptation step size
        
        # Frequency analysis
        self.freq_bins = np.fft.fftfreq(chunk_size, 1/sample_rate)
        self.voice_freq_mask = self._create_voice_frequency_mask()
        
        # High-pass filter for noise reduction
        self.highpass_filter = self._create_highpass_filter()
        
        print("[AudioFilter] Initialized with advanced filtering")
    
    def _create_voice_frequency_mask(self):
        """Create frequency mask for human voice range (85Hz - 8kHz)"""
        mask = np.zeros(len(self.freq_bins), dtype=bool)
        voice_range = (self.freq_bins >= 85) & (self.freq_bins <= 8000)
        mask[voice_range] = True
        return mask
    
    def _create_highpass_filter(self):
        """Create high-pass filter to remove low-frequency noise"""
        nyquist = self.sample_rate / 2
        cutoff = 80  # Hz
        b, a = butter(4, cutoff / nyquist, btype='high')
        return (b, a)
    
    def set_agent_speaking(self, speaking: bool):
        """Update agent speaking state for echo suppression"""
        self.agent_speaking = speaking
        if speaking:
            print("[AudioFilter] Agent speaking - enabling echo suppression")
        else:
            print("[AudioFilter] Agent finished - disabling echo suppression")
    
    def update_agent_audio(self, audio_data: np.ndarray):
        """Update reference audio for echo cancellation"""
        self.agent_audio_buffer.extend(audio_data)
    
    def calculate_audio_level(self, audio_data: np.ndarray) -> float:
        """Calculate RMS audio level in dB"""
        rms = np.sqrt(np.mean(audio_data ** 2))
        if rms < 1e-10:
            return -80  # Very quiet
        return 20 * np.log10(rms)
    
    def detect_voice_activity(self, audio_data: np.ndarray) -> bool:
        """Advanced voice activity detection using multiple features"""
        
        # 1. Energy-based detection
        audio_level = self.calculate_audio_level(audio_data)
        energy_active = audio_level > self.vad_threshold
        
        # 2. Frequency-based detection
        freq_active = self._analyze_voice_frequencies(audio_data)
        
        # 3. Zero-crossing rate (voice has moderate ZCR)
        zcr_active = self._analyze_zero_crossing_rate(audio_data)
        
        # 4. Spectral rolloff (voice energy concentrated in lower frequencies)
        spectral_active = self._analyze_spectral_rolloff(audio_data)
        
        # Combine features
        voice_features = [energy_active, freq_active, zcr_active, spectral_active]
        voice_score = sum(voice_features) / len(voice_features)
        
        # Require at least 50% of features to indicate voice
        is_voice = voice_score >= 0.5
        
        # Update silence counter
        if is_voice:
            self.silence_counter = 0
        else:
            self.silence_counter += 1
        
        # Consider voice active if recently detected
        self.voice_active = is_voice or (self.silence_counter < self.silence_threshold)
        
        return self.voice_active
    
    def _analyze_voice_frequencies(self, audio_data: np.ndarray) -> bool:
        """Analyze frequency content for voice characteristics"""
        fft = np.fft.fft(audio_data)
        magnitude = np.abs(fft[:len(fft)//2])
        
        # Focus on voice frequency range
        voice_energy = np.sum(magnitude[self.voice_freq_mask[:len(magnitude)]])
        total_energy = np.sum(magnitude)
        
        if total_energy < 1e-10:
            return False
        
        voice_ratio = voice_energy / total_energy
        return voice_ratio > 0.3
    
    def _analyze_zero_crossing_rate(self, audio_data: np.ndarray) -> bool:
        """Analyze zero crossing rate - voice has moderate ZCR"""
        zero_crossings = np.sum(np.diff(np.sign(audio_data)) != 0)
        zcr = zero_crossings / len(audio_data)
        
        # Voice typically has ZCR between 0.1 and 0.3
        return 0.05 < zcr < 0.4
    
    def _analyze_spectral_rolloff(self, audio_data: np.ndarray) -> bool:
        """Analyze spectral rolloff - voice energy concentrated in lower frequencies"""
        fft = np.fft.fft(audio_data)
        magnitude = np.abs(fft[:len(fft)//2])
        
        if np.sum(magnitude) < 1e-10:
            return False
        
        # Find frequency below which 85% of energy is contained
        cumulative_energy = np.cumsum(magnitude)
        total_energy = cumulative_energy[-1]
        rolloff_idx = np.where(cumulative_energy >= 0.85 * total_energy)[0]
        
        if len(rolloff_idx) == 0:
            return False
        
        rolloff_freq = self.freq_bins[rolloff_idx[0]]
        
        # Voice typically has rolloff below 4kHz
        return rolloff_freq < 4000
    
    def apply_noise_gate(self, audio_data: np.ndarray) -> np.ndarray:
        """Apply noise gate to suppress low-level noise"""
        audio_level = self.calculate_audio_level(audio_data)
        
        if audio_level < self.noise_gate_threshold:
            # Apply gradual attenuation instead of hard cutoff
            attenuation = max(0.1, (audio_level - self.noise_gate_threshold + 20) / 20)
            return audio_data * attenuation
        
        return audio_data
    
    def apply_highpass_filter(self, audio_data: np.ndarray) -> np.ndarray:
        """Apply high-pass filter to remove low-frequency noise"""
        try:
            b, a = self.highpass_filter
            filtered = filtfilt(b, a, audio_data)
            return filtered.astype(audio_data.dtype)
        except Exception:
            return audio_data
    
    def apply_echo_cancellation(self, audio_data: np.ndarray) -> np.ndarray:
        """Apply adaptive echo cancellation using LMS algorithm"""
        if not self.agent_speaking or len(self.agent_audio_buffer) < self.adaptive_filter_length:
            return audio_data
        
        try:
            # Get reference signal (agent audio)
            reference = np.array(list(self.agent_audio_buffer)[-self.adaptive_filter_length:])
            
            # Apply adaptive filter
            filtered_audio = np.copy(audio_data)
            
            for i in range(len(audio_data)):
                if i < len(reference):
                    # Estimate echo
                    echo_estimate = np.dot(self.adaptive_filter_weights[:i+1], reference[:i+1])
                    
                    # Remove echo estimate
                    filtered_audio[i] = audio_data[i] - echo_estimate * self.echo_suppression_level
                    
                    # Update filter weights using LMS
                    error = filtered_audio[i]
                    if i > 0:
                        self.adaptive_filter_weights[:i] += self.mu * error * reference[:i]
            
            return filtered_audio.astype(audio_data.dtype)
            
        except Exception as e:
            print(f"[AudioFilter] Echo cancellation error: {e}")
            return audio_data
    
    def apply_spectral_subtraction(self, audio_data: np.ndarray) -> np.ndarray:
        """Apply spectral subtraction for noise reduction"""
        if self.noise_profile is None:
            return audio_data
        
        try:
            # Convert to frequency domain
            fft = np.fft.fft(audio_data)
            magnitude = np.abs(fft)
            phase = np.angle(fft)
            
            # Subtract noise spectrum
            clean_magnitude = magnitude - self.noise_profile * 2.0
            clean_magnitude = np.maximum(clean_magnitude, magnitude * 0.1)  # Floor at 10%
            
            # Reconstruct signal
            clean_fft = clean_magnitude * np.exp(1j * phase)
            clean_audio = np.real(np.fft.ifft(clean_fft))
            
            return clean_audio.astype(audio_data.dtype)
            
        except Exception:
            return audio_data
    
    def update_noise_profile(self, audio_data: np.ndarray):
        """Update noise profile during silent periods"""
        if not self.voice_active:
            fft = np.fft.fft(audio_data)
            magnitude = np.abs(fft)
            
            if self.noise_profile is None:
                self.noise_profile = magnitude
            else:
                # Exponential moving average
                alpha = 0.1
                self.noise_profile = alpha * magnitude + (1 - alpha) * self.noise_profile
    
    def process_audio(self, audio_data: bytes) -> tuple[bytes, bool]:
        """Main audio processing pipeline"""
        try:
            # Convert bytes to numpy array
            audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
            audio_np = audio_np / 32768.0  # Normalize to [-1, 1]
            
            # Update audio buffer
            self.audio_buffer.extend(audio_np)
            
            # 1. Voice Activity Detection
            voice_detected = self.detect_voice_activity(audio_np)
            
            # 2. Update noise profile during silence
            self.update_noise_profile(audio_np)
            
            # Skip processing if no voice and agent not speaking (avoid feedback)
            if not voice_detected and not self.agent_speaking:
                # Return silence or minimal audio
                silent_audio = np.zeros_like(audio_np) * 0.1
                silent_bytes = (silent_audio * 32768).astype(np.int16).tobytes()
                return silent_bytes, False
            
            # 3. Apply high-pass filter
            filtered_audio = self.apply_highpass_filter(audio_np)
            
            # 4. Apply noise gate
            filtered_audio = self.apply_noise_gate(filtered_audio)
            
            # 5. Apply echo cancellation if agent is speaking
            if self.agent_speaking:
                filtered_audio = self.apply_echo_cancellation(filtered_audio)
            
            # 6. Apply spectral subtraction
            filtered_audio = self.apply_spectral_subtraction(filtered_audio)
            
            # 7. Normalize and convert back to bytes
            filtered_audio = np.clip(filtered_audio, -1.0, 1.0)
            filtered_bytes = (filtered_audio * 32768).astype(np.int16).tobytes()
            
            # Log processing status
            if voice_detected:
                audio_level = self.calculate_audio_level(audio_np)
                print(f"[AudioFilter] Voice detected: {audio_level:.1f}dB, Echo suppression: {'ON' if self.agent_speaking else 'OFF'}")
            
            return filtered_bytes, voice_detected
            
        except Exception as e:
            print(f"[AudioFilter] Processing error: {e}")
            return audio_data, True  # Return original on error


class AudioLoop:
    def __init__(self):
        self.audio_in_queue = None
        self.out_queue = None

        self.session = None

        self.audio_stream = None

        self.receive_audio_task = None
        self.play_audio_task = None
        
        # Initialize audio filter
        self.audio_filter = AudioFilter(
            sample_rate=SEND_SAMPLE_RATE,
            chunk_size=CHUNK_SIZE
        )
        
        # Agent state tracking
        self.agent_currently_speaking = False

    async def handle_tool_call(self, tool_call):
        function_responses = []
        for fc in tool_call.function_calls:
            print("TOOL Used: ", fc.name)
            func_generator = get_tool(ASSISTANT_NAME, fc.name)
            resp = func_generator(**fc.args)
            function_response = types.FunctionResponse(
                id=fc.id,
                name=fc.name,
                response={"result": resp},
                will_continue=False,
            )
            function_responses.append(function_response)
        await self.session.send_tool_response(function_responses=function_responses)

    async def listen_audio(self):
        """Enhanced audio input with filtering"""
        mic_info = pya.get_default_input_device_info()
        self.audio_stream = await asyncio.to_thread(
            pya.open,
            format=FORMAT,
            channels=CHANNELS,
            rate=SEND_SAMPLE_RATE,
            input=True,
            input_device_index=mic_info["index"],
            frames_per_buffer=CHUNK_SIZE,
        )
        
        if __debug__:
            kwargs = {"exception_on_overflow": False}
        else:
            kwargs = {}
        
        print("[AudioLoop] Starting filtered audio input...")
        
        while True:
            # Read raw audio data
            raw_data = await asyncio.to_thread(self.audio_stream.read, CHUNK_SIZE, **kwargs)
            
            # Apply audio filtering
            filtered_data, voice_detected = self.audio_filter.process_audio(raw_data)
            
            # Only send audio if voice is detected or we're in a conversation
            if voice_detected or self.agent_currently_speaking:
                await self.out_queue.put({
                    "data": filtered_data, 
                    "mime_type": "audio/pcm"
                })

    async def send_realtime(self):
        while True:
            msg = await self.out_queue.get()
            await self.session.send_realtime_input(audio=msg)

    async def receive_audio(self):
        """Background task to read from websocket and handle agent audio"""
        while True:
            turn = self.session.receive()
            async for response in turn:
                if data := response.data:
                    # Agent is sending audio - update filter state
                    if not self.agent_currently_speaking:
                        self.agent_currently_speaking = True
                        self.audio_filter.set_agent_speaking(True)
                        print("[AudioLoop] Agent started speaking")
                    
                    # Update echo cancellation reference
                    agent_audio_np = np.frombuffer(data, dtype=np.int16).astype(np.float32)
                    self.audio_filter.update_agent_audio(agent_audio_np)
                    
                    # Queue for playback
                    self.audio_in_queue.put_nowait(data)
                    continue
                
                if text := response.text:
                    print(text, end="")

                if tool_call := response.tool_call:
                    await self.handle_tool_call(tool_call)

            # Turn complete - agent finished speaking
            if self.agent_currently_speaking:
                self.agent_currently_speaking = False
                self.audio_filter.set_agent_speaking(False)
                print("[AudioLoop] Agent finished speaking")

            # Clear queued audio on interruption
            while not self.audio_in_queue.empty():
                self.audio_in_queue.get_nowait()

    async def play_audio(self):
        stream = await asyncio.to_thread(
            pya.open,
            format=FORMAT,
            channels=CHANNELS,
            rate=RECEIVE_SAMPLE_RATE,
            output=True,
        )
        while True:
            bytestream = await self.audio_in_queue.get()
            await asyncio.to_thread(stream.write, bytestream)

    async def run(self):
        print("Starting Gemini Live with Advanced Audio Filtering...")
        print("Features: Echo Cancellation, Noise Suppression, Voice Activity Detection")
        print("Please start speaking... start by saying hello...!")
        
        try:
            async with (
                client.aio.live.connect(model=MODEL, config=CONFIG) as session,
                asyncio.TaskGroup() as tg,
            ):
                self.session = session

                self.audio_in_queue = asyncio.Queue()
                self.out_queue = asyncio.Queue(maxsize=5)

                tg.create_task(self.send_realtime())
                tg.create_task(self.listen_audio())
                tg.create_task(self.receive_audio())
                tg.create_task(self.play_audio())
        except asyncio.CancelledError:
            pass
        except ExceptionGroup as EG:  # noqa: F821
            if self.audio_stream:
                self.audio_stream.close()
            traceback.print_exception(EG)


if __name__ == "__main__":
    loop = AudioLoop()
    asyncio.run(loop.run())
