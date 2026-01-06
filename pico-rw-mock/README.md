# Pico RW Mock

Raspberry Pi Pico + DRV8833 でリアクションホイールの回転をモーターで模擬するファームウェア。
USB HID プロトコルでシミュレータから回転速度を受信し、モーターを制御。

## Hardware

- Raspberry Pi Pico
- DRV8833 motor driver
- DC motor (FA-130 compatible)
- USB cable

## Pin Assignment

| Pico GPIO | DRV8833 | Description |
|-----------|---------|-------------|
| GPIO16    | AIN1    | Motor A PWM+ |
| GPIO17    | AIN2    | Motor A PWM- |
| GPIO18    | nSLEEP  | Sleep control (HIGH = active) |

### PWM Configuration

- Frequency: ~10kHz
- TOP: 2500
- Divider: 5

## USB

- VID: `0x2E8A` (Raspberry Pi)
- PID: `0x0B33` (Custom)
- Protocol: USB HID

### HID Protocol

**Output Report (Host → Device):**
| Byte | Type | Description |
|------|------|-------------|
| 0    | u8   | Report ID (0) |
| 1-2  | i16  | Normalized speed: -32767 to +32767 (-100% to +100%) |

シミュレータのRW速度（0-900 rad/s）を正規化して送信。
Picoはこれをモーターduty cycle（0-100%）にマッピング。

## Build & Flash

```bash
cargo run --release
```

## Usage

1. Build and flash firmware to Pico:
   ```bash
   cargo run --release
   ```

2. Start backend (will auto-connect to Pico):
   ```bash
   cd ..
   make backend
   ```

3. Run simulation - motor will visualize RW X-axis speed

## Features

- **Normalized speed control**: RW max speed (900 rad/s) → 100% motor duty
- **Bidirectional rotation**: Forward/reverse based on RW direction
- **Kickstart logic**: 100% duty for 150ms when starting/changing direction
- **Minimum duty**: 40% minimum to ensure reliable rotation
