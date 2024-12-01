from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import uvicorn
import sounddevice as sd
import numpy as np
import asyncio
from typing import Optional, Dict, List
import logging
import time
from queue import Queue
import threading
from contextlib import asynccontextmanager
import pyaudio
import wave
from dataclasses import dataclass
import os
from pathlib import Path
import tempfile
from piper import PiperVoice

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("TTSService")

class TextRequest(BaseModel):
    """Text request model"""
    text: str

class AudioRequest(BaseModel):
    """Audio request model"""
    audio_data: List[float]
    sample_rate: int = 22050

class AudioConfig:
    """Audio configuration for Seeed ReSpeaker"""
    RATE = 48000  # Native rate for Seeed ReSpeaker
    CHANNELS = 2
    FORMAT = pyaudio.paFloat32
    CHUNK = 1024  # Reduced for better latency
    BUFFER_SIZE = 4096

class QueueItem:
    """Represents a queued audio item"""
    def __init__(self, audio_data: np.ndarray, sample_rate: int):
        self.id = f"audio_{int(time.time() * 1000)}"
        self.audio_data = audio_data
        self.sample_rate = sample_rate
        self.timestamp = time.time()
        self.status = "queued"

class AudioService:
    """Manages audio playback with device handling"""
    def __init__(self, audio_config: AudioConfig):
        self.config = audio_config
        self.queue: Queue = Queue()
        self.items: Dict[str, QueueItem] = {}
        self.currently_playing: Optional[str] = None
        self.is_playing = threading.Event()
        self._stop_requested = threading.Event()
        self._player_thread = None
        self._pa = None
        self._stream = None
        self._device_setup()

    def _device_setup(self):
        """Initialize PyAudio with Seeed ReSpeaker configuration"""
        try:
            self._pa = pyaudio.PyAudio()
            device_index = None

            # Find Seeed ReSpeaker device
            for i in range(self._pa.get_device_count()):
                dev_info = self._pa.get_device_info_by_index(i)
                if 'seeed' in dev_info['name'].lower():
                    device_index = i
                    logger.info(f"Found Seeed ReSpeaker: {dev_info['name']}")
                    break

            if device_index is None:
                device_index = self._pa.get_default_output_device_info()['index']
                logger.info("Using default output device")

            # Open audio stream with optimized settings
            self._stream = self._pa.open(
                rate=self.config.RATE,
                channels=self.config.CHANNELS,
                format=self.config.FORMAT,
                output=True,
                output_device_index=device_index,
                frames_per_buffer=self.config.CHUNK,
                start=False
            )
            
        except Exception as e:
            logger.error(f"Audio device setup error: {e}")
            self.cleanup()
            raise

    def start(self):
        """Start the audio player thread"""
        self._stop_requested.clear()
        self._player_thread = threading.Thread(target=self._player_worker, daemon=True)
        self._player_thread.start()

    def _player_worker(self):
        """Worker thread for playing audio"""
        while not self._stop_requested.is_set():
            try:
                if not self.queue.empty() and self._stream:
                    item = self.queue.get()
                    self.currently_playing = item.id
                    self.is_playing.set()
                    item.status = "playing"

                    try:
                        # Ensure proper sample rate and format
                        audio_data = item.audio_data
                        if item.sample_rate != self.config.RATE:
                            audio_data = self._resample_audio(
                                audio_data,
                                item.sample_rate,
                                self.config.RATE
                            )

                        # Convert to stereo if mono
                        if len(audio_data.shape) == 1:
                            audio_data = np.column_stack((audio_data, audio_data))

                        # Normalize audio levels
                        max_val = np.max(np.abs(audio_data))
                        if max_val > 0:
                            audio_data = audio_data / max_val * 0.9  # Leave some headroom

                        # Start stream if needed
                        if not self._stream.is_active():
                            self._stream.start_stream()

                        # Play in chunks with proper buffer management
                        for i in range(0, len(audio_data), self.config.CHUNK):
                            if self._stop_requested.is_set():
                                break
                            chunk = audio_data[i:i + self.config.CHUNK]
                            if len(chunk) < self.config.CHUNK:
                                chunk = np.pad(
                                    chunk,
                                    ((0, self.config.CHUNK - len(chunk)), (0, 0)),
                                    mode='constant'
                                )
                            self._stream.write(chunk.tobytes())

                        item.status = "completed"

                    except Exception as e:
                        logger.error(f"Playback error: {e}")
                        item.status = "failed"
                    finally:
                        if self._stream and self._stream.is_active():
                            self._stream.stop_stream()

                    self.currently_playing = None
                    self.is_playing.clear()
                else:
                    time.sleep(0.1)

            except Exception as e:
                logger.error(f"Player worker error: {e}")
                time.sleep(0.1)

    def _resample_audio(self, audio_data: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
        """High-quality resampling using linear interpolation"""
        if src_rate == dst_rate:
            return audio_data

        # Normalize audio to float32 between -1 and 1
        if audio_data.dtype != np.float32:
            audio_data = audio_data.astype(np.float32)
            if audio_data.max() > 1.0:
                audio_data = audio_data / 32768.0

        duration = len(audio_data) / src_rate
        time_old = np.linspace(0, duration, len(audio_data))
        time_new = np.linspace(0, duration, int(len(audio_data) * dst_rate / src_rate))
        
        if len(audio_data.shape) == 2:  # Stereo
            resampled = np.zeros((len(time_new), 2), dtype=np.float32)
            for channel in range(2):
                resampled[:, channel] = np.interp(time_new, time_old, audio_data[:, channel])
        else:  # Mono
            resampled = np.interp(time_new, time_old, audio_data)
            
        return resampled.astype(np.float32)

    def add_item(self, audio_data: np.ndarray, sample_rate: int) -> str:
        """Add audio to the queue"""
        item = QueueItem(audio_data, sample_rate)
        self.items[item.id] = item
        self.queue.put(item)
        return item.id

    def stop(self):
        """Stop playback and clear queue"""
        self._stop_requested.set()
        if self._stream:
            self._stream.stop_stream()
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except:
                pass
        self.currently_playing = None
        self.is_playing.clear()

    def cleanup(self):
        """Clean up resources"""
        self.stop()
        if self._stream:
            self._stream.close()
        if self._pa:
            self._pa.terminate()
        self._stream = None
        self._pa = None

    def get_status(self) -> dict:
        """Get current queue status"""
        return {
            "currently_playing": self.currently_playing,
            "queue_size": self.queue.qsize(),
            "is_playing": self.is_playing.is_set(),
            "items": [
                {
                    "id": id,
                    "status": item.status,
                    "queued_at": item.timestamp
                }
                for id, item in self.items.items()
            ]
        }

class PiperTTSService:
    """Handles Piper TTS operations"""
    def __init__(self):
        # Match existing directory structure
        self.model_path = "./piper-models/sv_SE-nst-medium.onnx"  # Note the underscore
        self.config_path = "./piper-models/sv_SE-nst-medium.onnx.json"  # Note the underscore
        self.sample_rate = 22050
        self.voice = None
        self.temp_dir = tempfile.mkdtemp(prefix='piper_')
        self._setup_piper()

    def _setup_piper(self):
        """Initialize Piper TTS"""
        try:
            if not os.path.exists(self.model_path):
                raise FileNotFoundError(f"Model not found at {self.model_path}")
            if not os.path.exists(self.config_path):
                raise FileNotFoundError(f"Config not found at {self.config_path}")
                
            self.voice = PiperVoice.load(self.model_path, self.config_path)
            logger.info("Piper TTS initialized successfully")
        except Exception as e:
            logger.error(f"Piper initialization error: {e}")
            raise

    def synthesize(self, text: str) -> tuple[np.ndarray, int]:
        """Synthesize text to audio"""
        try:
            temp_path = os.path.join(self.temp_dir, f"temp_{threading.get_ident()}.wav")
            
            try:
                with wave.open(temp_path, 'wb') as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(self.sample_rate)
                    self.voice.synthesize(text, wav_file)

                with wave.open(temp_path, 'rb') as wav_file:
                    audio_data = np.frombuffer(
                        wav_file.readframes(wav_file.getnframes()),
                        dtype=np.int16
                    ).astype(np.float32) / 32768.0

                return audio_data, self.sample_rate

            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)

        except Exception as e:
            logger.error(f"Synthesis error: {e}")
            raise

    def cleanup(self):
        """Clean up resources"""
        self.voice = None
        if os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)

class TTSServiceManager:
    """Main service manager"""
    def __init__(self):
        self.audio_config = AudioConfig()
        self.audio_service = AudioService(self.audio_config)
        self.piper_service = PiperTTSService()
        
    async def start(self):
        """Start services"""
        self.audio_service.start()
        
    async def cleanup(self):
        """Cleanup all resources"""
        self.audio_service.cleanup()
        self.piper_service.cleanup()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    service = TTSServiceManager()
    app.state.service = service
    await service.start()
    yield
    # Shutdown
    await service.cleanup()

app = FastAPI(lifespan=lifespan)

@app.post("/text")
async def text_to_speech(request: TextRequest):
    """Convert text to speech and queue for playback"""
    try:
        service = app.state.service
        audio_data, sample_rate = service.piper_service.synthesize(request.text)
        task_id = service.audio_service.add_item(audio_data, sample_rate)
        return {"task_id": task_id}
    except Exception as e:
        logger.error(f"Text-to-speech error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/play")
async def play_audio(request: AudioRequest):
    """Queue raw audio for playback"""
    try:
        service = app.state.service
        audio_data = np.array(request.audio_data, dtype=np.float32)
        task_id = service.audio_service.add_item(audio_data, request.sample_rate)
        return {"task_id": task_id}
    except Exception as e:
        logger.error(f"Play audio error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/stop")
async def stop_playback():
    """Stop playback and clear queue"""
    try:
        service = app.state.service
        service.audio_service.stop()
        return {"status": "stopped"}
    except Exception as e:
        logger.error(f"Stop playback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status")
async def get_status():
    """Get service status"""
    try:
        service = app.state.service
        return service.audio_service.get_status()
    except Exception as e:
        logger.error(f"Status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8912,
        log_level="info"
    )