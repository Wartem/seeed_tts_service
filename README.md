# FastAPI TTS Service

A high-performance Text-to-Speech (TTS) service built with FastAPI and Piper TTS, featuring real-time audio playback and a command-line interface. The service is optimized for the Seeed ReSpeaker device but works with standard audio output devices as well.

## Features

- Real-time text-to-speech synthesis using Piper TTS
- Optimized audio playback with device-specific configurations
- Audio queue management with playback controls
- REST API endpoints for text input and audio control
- Interactive CLI client with rich terminal interface
- Comprehensive status monitoring and logging
- Support for custom sample rates and audio resampling
- Built-in error handling and resource management

## Prerequisites

- Python 3.8+
- Piper TTS models
- PyAudio
- Seeed ReSpeaker (optional)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/Wartem/fastapi-tts-service
cd fastapi-tts-service
```

2. Install dependencies:
```bash
pip install fastapi uvicorn sounddevice numpy pyaudio piper-tts rich aiohttp
```

3. Download Piper TTS models:
```bash
mkdir piper-models
# Download your preferred model and place in piper-models directory
# Example: sv_SE-nst-medium.onnx and sv_SE-nst-medium.onnx.json
```

## Usage

### Starting the Server

1. Run the FastAPI server:
```bash
python server.py
```

The server will start on `http://localhost:8912`

### Using the CLI Client

1. Run the client:
```bash
python client.py
```

2. Use the interactive menu to:
   - Send text for speech synthesis
   - Stop playback
   - Check service status
   - Exit the application

## API Endpoints

- `POST /text`: Convert text to speech
  ```json
  {
    "text": "Text to be spoken"
  }
  ```

- `POST /play`: Queue raw audio for playback
  ```json
  {
    "audio_data": [float_array],
    "sample_rate": 22050
  }
  ```

- `POST /stop`: Stop current playback and clear queue

- `GET /status`: Get service status

## Configuration

### Audio Settings

Default audio configuration in `server.py`:
```python
RATE = 48000  # Sample rate
CHANNELS = 2  # Stereo output
FORMAT = pyaudio.paFloat32
CHUNK = 1024  # Buffer size
```

### TTS Model

Default Piper model configuration in `server.py`:
```python
model_path = "./piper-models/sv_SE-nst-medium.onnx"
config_path = "./piper-models/sv_SE-nst-medium.onnx.json"
```

## Error Handling

The service includes comprehensive error handling:
- Audio device initialization failures
- TTS synthesis errors
- Network communication issues
- Resource cleanup on shutdown

## Technical Details

- **Audio Processing**: High-quality resampling with linear interpolation
- **Queue Management**: Thread-safe audio queue with status tracking
- **Device Management**: Automatic Seeed ReSpeaker detection with fallback
- **Resource Management**: Proper cleanup of audio resources and temporary files
- **Async Support**: Full async/await support in both server and client

## System Requirements

- CPU: 1+ cores
- RAM: 2GB+ recommended
- Storage: 100MB+ for models
- Network: Local network access
- Audio: Compatible audio output device

## Troubleshooting

1. **Audio Device Not Found**:
   - Check audio device connections
   - Verify PyAudio installation
   - Check device permissions

2. **Model Loading Failed**:
   - Verify model files exist in correct location
   - Check model file permissions
   - Ensure correct model format

3. **Playback Issues**:
   - Check audio device settings
   - Verify audio format compatibility
   - Check system volume levels
