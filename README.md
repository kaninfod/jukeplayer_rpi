# Jukeplayer Raspberry Pi Client

Hardware client for Jukeplayer running on Raspberry Pi.

## Features

- GPIO button control for music playback
- Rotary encoder for volume control
- NFC/RFID card reader for album selection
- TFT display for track information
- WebSocket connection to backend for real-time updates
- HTTP client for sending commands to backend

## Setup

### On Raspberry Pi

```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install system GPIO library
sudo apt-get install python3-lgpio

# Copy environment variables
cp .env.example .env

# Edit .env with:
# - BACKEND_URL (IP of machine running backend)
# - GPIO pin numbers for your wiring
```

### For Development on Mac

```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies (minus GPIO which is Pi-specific)
pip install -r requirements.txt

# Copy environment variables
cp .env.example .env

# Set HARDWARE_MODE=mock to use mock hardware
```

## Running

```bash
python run.py
```

## Hardware Connections

- **Button 1 (GPIO 17)**: Previous track
- **Button 2 (GPIO 27)**: Play/Pause
- **Button 3 (GPIO 22)**: Next track
- **Button 4 (GPIO 23)**: Stop (long press)
- **Button 5 (GPIO 24)**: Custom function

- **Rotary Encoder A (GPIO 5)**: Volume control
- **Rotary Encoder B (GPIO 6)**: Volume control

- **NFC Card Switch (GPIO 25)**: Detect card insertion
- **NFC Reader**: I2C bus for PN532 reader

- **Display**: SPI bus for ILI9488 TFT display

## Architecture

- **Hardware** (`app/hardware/`): GPIO, buttons, RFID, display drivers
- **Client** (`app/client/`): API client, WebSocket client, event translator
- **UI** (`app/ui/`): Screen manager, display rendering
- **Core** (`app/core/`): Local event bus

## Communication Flow

1. Hardware event (button press) → Local event bus
2. Event translator → HTTP API call to backend
3. Backend processes → WebSocket broadcast
4. Pi WebSocket client receives → Updates display

## Development

For Mac development without Raspberry Pi hardware:
- All hardware events are mocked
- Display output goes to console/fake display
- API calls to backend work normally

Test with: `HARDWARE_MODE=mock python run.py`
