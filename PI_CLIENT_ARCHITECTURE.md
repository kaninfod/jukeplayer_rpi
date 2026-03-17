# Pi Client Architecture Guide

## Overview

The Pi client is a hardware manager that translates physical device interactions (buttons, encoders, card readers) into API calls to the backend server, and receives real-time state updates via WebSocket to drive the display.

## Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Pi Client Application                     │
│                                                              │
│  ┌──────────────┐      ┌──────────────────┐                │
│  │  Hardware    │      │   Event          │                │
│  │  Manager     │─────▶│ Translator       │                │
│  │              │      │                  │                │
│  │ - Buttons    │      │ - Button 1→prev  │                │
│  │ - Rotary     │      │ - Button 2→play  │                │
│  │ - RFID       │      │ - Rotary→volume  │                │
│  │ - Display    │      │ - RFID→album     │                │
│  └──────────────┘      └────────┬─────────┘                │
│                 ─────────────────▼──────────────────        │
│                          ┌──────────────┐                   │
│                          │  API Client  │                   │
│                          │              │                   │
│                          │ HTTP requests│                   │
│                          │ to Backend   │                   │
│                          └──────────────┘                   │
└──────────────────────────────────┼──────────────────────────┘
                                    │
                    Backend Server (REST API)
                    http://192.168.1.100:8000
                                    │
                 ┌──────────────────┴──────────────────┐
                 │                                     │
        ┌─────────▼────────┐              ┌────────────▼──────┐
        │  Process Request │              │ Broadcast State   │
        │  Update Database │              │ via WebSocket     │
        │                  │              │                   │
        └──────────────────┘              └────────────┬──────┘
                                            (to all     │
                                             clients)   │
                         ┌──────────────────────────────┘
                         │
        ┌────────────────▼──────────────────┐
        │   WebSocket Client                │
        │   ws://192.168.1.100:8000/ws/...  │
        │                                   │
        │   Receives: Backend State Updates │
        └────────────┬──────────────────────┘
                     │
         ┌───────────▼──────────┐
         │  State Manager       │
         │                      │
         │ - Caches state       │
         │ - Notifies UI        │
         │ - Tracks connection  │
         └───────────┬──────────┘
                     │
        ┌────────────▼──────────┐
        │  Screen Manager       │
        │  (UI Layer)           │
        │  Updates Display with │
        │  Current Track, Vol   │
        └──────────────────────┘
```

## Module Responsibilities

### 1. **config.py** - Configuration Management
- **Purpose**: Load and expose configuration settings
- **Key Settings**:
  - Backend URLs (HTTP + WebSocket)
  - GPIO pin assignments (5 buttons, rotary encoder, RFID, display)
  - Hardware mode (real vs mock)
  - Connection parameters (heartbeat, reconnect delays)
- **Usage**: `from app.config import config`

### 2. **api_client.py** - Backend Communication
- **Class**: `BackendAPIClient`
- **Responsibilities**:
  - Send HTTP requests to backend
  - Handle retries and errors
  - Provide type-safe method wrappers
- **Key Methods**:
  - Playback: `next_track()`, `previous_track()`, `play_pause()`, `stop()`
  - Albums: `play_album_from_albumid()`, `play_album_from_rfid()`
  - Volume: `volume_up()`, `volume_down()`, `set_volume()`
  - Display: `set_brightness()`, `get_brightness()`
  - System: `request_shutdown()`, `request_reboot()`

### 3. **websocket_client.py** - Real-time Updates
- **Class**: `BackendWebSocketClient`
- **Responsibilities**:
  - Maintain persistent WebSocket connection
  - Listen for incoming state updates
  - Emit events to subscribers
  - Handle reconnection attempts gracefully
- **Key Methods**:
  - `connect()`: Establish connection
  - `on(event_type, callback)`: Register listeners
  - `close()`: Graceful disconnect
  - `is_connected()`: Check connection status

### 4. **event_translator.py** - Hardware→API Bridge
- **Class**: `EventTranslator`
- **Responsibilities**:
  - Translate hardware events to API calls
  - Map button presses to actions
  - Handle rotary encoder turns for volume
  - Process RFID card reads
- **Key Methods**:
  - `on_button_pressed(button_num)`: Handle button press
  - `on_rotary_turn(direction, steps)`: Handle encoder
  - `on_rfid_read(card_id)`: Handle card scan
  - `on_card_inserted()`: Handle card insertion

### 5. **state_manager.py** - Backend State Cache
- **Classes**:
  - `PlaybackState`: Immutable snapshot of backend state
  - `StateManager`: Caches and broadcasts state changes
- **Responsibilities**:
  - Cache latest backend state
  - Notify subscribers of specific changes
  - Provide query methods for common properties
- **Key Features**:
  - Subscriber pattern for multiple listeners
  - Event types: state_changed, track_changed, playback_changed, volume_changed
  - Properties: `is_playing`, `volume`, `brightness`, `backend_connected`

### 6. **connection_monitor.py** - Connection Health
- **Class**: `ConnectionMonitor`
- **Responsibilities**:
  - Monitor WebSocket connection health
  - Detect disconnections via heartbeat
  - Attempt reconnections with exponential backoff
  - Notify UI of connection state changes
- **Key Features**:
  - Configurable heartbeat interval (default: 30s)
  - Exponential backoff reconnection (configurable max attempts)
  - Status reporting for debugging

### 7. **main.py** - Application Orchestrator
- **Class**: `PiClientApp`
- **Responsibilities**:
  - Initialize all subsystems
  - Wire up event callbacks
  - Manage application lifecycle
  - Handle graceful shutdown
- **Initialization Sequence**:
  1. Initialize hardware (real or mock)
  2. Initialize UI/display
  3. Register hardware callbacks with event translator
  4. Register WebSocket callbacks with state manager
  5. Start connection monitor
  6. Connect to backend
  7. Enter event loop

## Data Flow: Button Press → Display Update

```
1. User presses Button 2 (Play/Pause)
   ↓
2. HardwareManager detects press
   ↓
3. EventTranslator.on_button_pressed(button=2)
   ↓
4. APIClient.play_pause() → POST /api/mediaplayer/play_pause
   ↓
5. Backend processes, updates state, broadcasts via WebSocket
   ↓
6. WebSocketClient receives message
   ↓
7. StateManager.update_from_backend()
   ↓
8. StateManager notifies subscribers (state_changed, playback_changed events)
   ↓
9. ScreenManager.update_status(state) → Redraws display
   ↓
10. User sees "Now Playing: [Track Name]" on TFT
```

## Error Handling & Resilience

### Scenario: Backend Goes Down

```
1. Backend crashes
   ↓
2. WebSocket connection drops
   ↓
3. StateManager.notify_connection_lost()
   ↓
4. ConnectionMonitor detects (via heartbeat timeout)
   ↓
5. ScreenManager shows "Backend Disconnected"
   ↓
6. ConnectionMonitor begins exponential backoff reconnection attempts
   ↓
7. Once backend is back: ConnectionMonitor reconnects
   ↓
8. StateManager.notify_connection_restored()
   ↓
9. ScreenManager returns to normal display
```

### Scenario: User Presses Button While Disconnected

```
1. User presses button
   ↓
2. EventTranslator calls APIClient method
   ↓
3. APIClient gets HTTP error (backend unreachable)
   ↓
4. Error is logged, user continues
   ↓
5. Once backend reconnects, state queries will return current state
```

## Configuration via Environment Variables

Create a `.env` file in the workspace root:

```bash
# Backend connection
BACKEND_URL=http://192.168.1.100:8000
BACKEND_WS_URL=ws://192.168.1.100:8000/ws/mediaplayer/status

# Hardware mode
HARDWARE_MODE=real  # or "mock" for development

# GPIO pins (Raspberry Pi)
BUTTON_1_GPIO=14
BUTTON_2_GPIO=15
ROTARY_ENCODER_PIN_A=22
ROTARY_ENCODER_PIN_B=27
NFC_CARD_SWITCH_GPIO=4

# Connection monitoring
HEARTBEAT_INTERVAL=30
RECONNECT_DELAY=5
MAX_RECONNECT_ATTEMPTS=0  # 0 = infinite
```

## Running the Application

### Development Mode (Mac with Mock Hardware)

```bash
export HARDWARE_MODE=mock
export BACKEND_URL=http://127.0.0.1:8000
cd /path/to/Jukeplayer_rpi
python run.py
```

### Production Mode (Actual Pi)

```bash
cd /path/to/Jukeplayer_rpi
source venv/bin/activate
python run.py
```

## Testing

### Mock Hardware Mode
- Best for development on non-Pi systems
- Simulates button presses and hardware events
- Still connects to backend server (can be on Mac or actual server)
- Useful for testing state manager and UI without hardware

### Unit Testing Individual Components

```python
# Test StateManager
state = StateManager()
state.subscribe("state_changed", on_state_changed_callback)
await state.update_from_backend({"is_playing": True, ...})

# Test EventTranslator
translator = EventTranslator(api_client)
await translator.on_button_pressed({"button": 1})  # Calls api.previous_track()

# Test ConnectionMonitor
monitor = ConnectionMonitor(ws_client)
await monitor.start()
```

## Deployment Considerations

1. **GPIO Permissions**: On actual Pi, may need to run as sudo
2. **Backend Accessibility**: Ensure backend URL is reachable from Pi network
3. **Fonts**: Copy font files if using custom fonts
4. **SPI Device**: RFID reader needs SPI enabled on Pi
5. **Display**: ILI9488 display needs SPI and GPIO setup

## Future Enhancements

- [ ] Offline mode: cache album list, queue for sync when online
- [ ] Bluetooth audio output fallback
- [ ] Screen rotation based on sensor
- [ ] Custom button long-press actions
- [ ] Volume knob acceleration curve
- [ ] Display power saving (backlight timeout)
