"""Raspberry Pi Pico Reaction Wheel Controller via USB HID.

Controls physical motors to visualize reaction wheel rotation speeds.
Supports up to 3 axes (X, Y, Z) using separate Pico boards.

HID Protocol:
  Output Report (Host → Pico): [speed_normalized] (int16_t, little-endian)
    - Normalized speed: -32767 = -100%, 0 = stop, +32767 = +100%
    - Pico maps this to motor duty cycle (0-100%)

Multi-Axis Configuration:
  Each Pico identifies its axis via GPIO0/1 pins and sets USB Serial Number:
    - X-axis: "RW-X" (GPIO0=HIGH, GPIO1=HIGH - floating)
    - Y-axis: "RW-Y" (GPIO0=LOW, GPIO1=HIGH)
    - Z-axis: "RW-Z" (GPIO0=HIGH, GPIO1=LOW)
"""

import struct
import threading
import time
from typing import Optional

import numpy as np
from numpy.typing import NDArray

try:
    import hid
except ImportError:
    hid = None  # type: ignore

# USB VID/PID for Pico RW controller
# Using same as drv8833-motor for now
VID = 0x2E8A
PID = 0x0B33


class PicoRWController:
    """Controls up to 3 Raspberry Pi Picos for 3-axis RW visualization."""

    def __init__(self, vid: int = VID, pid: int = PID, max_rw_speed: float = 900.0):
        """Initialize controller (does not connect).

        Args:
            vid: USB Vendor ID
            pid: USB Product ID
            max_rw_speed: Maximum RW speed in rad/s (used for normalization)
        """
        if hid is None:
            raise ImportError("hid library not available. Install with: uv pip install hid")

        self.vid = vid
        self.pid = pid
        self.max_rw_speed = max_rw_speed

        # One HID device per axis
        self.device_x: Optional[hid.Device] = None
        self.device_y: Optional[hid.Device] = None
        self.device_z: Optional[hid.Device] = None

        # Track last commanded speeds for all axes
        self._last_speed = np.zeros(3)

        # Auto-reconnect management (background thread)
        self._reconnect_interval: float = 1.0  # Try reconnect every 1 second
        self._reconnect_thread: Optional[threading.Thread] = None
        self._reconnect_running: bool = False
        self._reconnect_lock = threading.Lock()

    def connect(self) -> dict[str, bool]:
        """Attempt to connect to all available Pico devices.

        Returns:
            Connection status per axis: {'x': True, 'y': False, 'z': True}
        """
        status = self._connect_devices()

        # Start background reconnection thread if not already running
        if not self._reconnect_running:
            self._reconnect_running = True
            self._reconnect_thread = threading.Thread(
                target=self._reconnect_background,
                daemon=True,
                name="PicoRW-Reconnect"
            )
            self._reconnect_thread.start()

        return status

    def _connect_devices(self) -> dict[str, bool]:
        """Internal method to connect to devices (thread-safe)."""
        devices = hid.enumerate(self.vid, self.pid)
        status = {'x': False, 'y': False, 'z': False}

        with self._reconnect_lock:
            for dev_info in devices:
                serial = dev_info.get('serial_number', '')

                try:
                    if serial == 'RW-X' and self.device_x is None:
                        self.device_x = hid.Device(path=dev_info['path'])
                        status['x'] = True
                        print(f"Connected to X-axis Pico: {dev_info['path']}")
                    elif serial == 'RW-Y' and self.device_y is None:
                        self.device_y = hid.Device(path=dev_info['path'])
                        status['y'] = True
                        print(f"Connected to Y-axis Pico: {dev_info['path']}")
                    elif serial == 'RW-Z' and self.device_z is None:
                        self.device_z = hid.Device(path=dev_info['path'])
                        status['z'] = True
                        print(f"Connected to Z-axis Pico: {dev_info['path']}")
                except (OSError, hid.HIDException) as e:
                    print(f"Failed to connect to {serial}: {e}")

        return status

    def _reconnect_background(self):
        """Background thread for automatic reconnection (non-blocking)."""
        while self._reconnect_running:
            try:
                # Check if any devices are disconnected
                with self._reconnect_lock:
                    need_reconnect = (
                        self.device_x is None or
                        self.device_y is None or
                        self.device_z is None
                    )

                if need_reconnect:
                    # Attempt reconnection (this blocking call runs in background)
                    self._connect_devices()

                # Sleep for reconnect interval
                time.sleep(self._reconnect_interval)

            except Exception as e:
                print(f"Error in reconnect thread: {e}")
                time.sleep(self._reconnect_interval)

    def disconnect(self):
        """Disconnect from all devices and stop reconnect thread."""
        # Stop reconnect thread
        self._reconnect_running = False
        if self._reconnect_thread and self._reconnect_thread.is_alive():
            self._reconnect_thread.join(timeout=2.0)

        # Close all devices
        with self._reconnect_lock:
            for device in [self.device_x, self.device_y, self.device_z]:
                if device:
                    try:
                        device.close()
                    except Exception:
                        pass
            self.device_x = None
            self.device_y = None
            self.device_z = None

    def is_connected(self) -> dict[str, bool]:
        """Check which axes are currently connected (thread-safe).

        Returns:
            Connection status per axis: {'x': True, 'y': False, 'z': True}
        """
        with self._reconnect_lock:
            return {
                'x': self.device_x is not None,
                'y': self.device_y is not None,
                'z': self.device_z is not None,
            }

    def set_speed(self, speed_rad_s: NDArray[np.float64]):
        """Set reaction wheel speeds for all axes (non-blocking).

        Args:
            speed_rad_s: [wx, wy, wz] in rad/s (shape: (3,))
        """
        if len(speed_rad_s) != 3:
            raise ValueError(f"Expected 3-element array, got {len(speed_rad_s)}")

        # Reconnection happens automatically in background thread
        self._send_to_device(self.device_x, speed_rad_s[0], 'X')
        self._send_to_device(self.device_y, speed_rad_s[1], 'Y')
        self._send_to_device(self.device_z, speed_rad_s[2], 'Z')

        self._last_speed = speed_rad_s.copy()

    def _send_to_device(self, device: Optional[hid.Device], speed: float, axis: str):
        """Send speed command to a single device (thread-safe).

        Args:
            device: HID device to send to (or None)
            speed: Speed in rad/s
            axis: Axis name ('X', 'Y', or 'Z') for logging
        """
        # Check device availability (lock-free fast path)
        if device is None:
            return  # Device not connected, silently skip

        # Normalize speed to ±100% based on max_rw_speed
        # -max_rw_speed -> -32767 (-100%)
        # 0 -> 0 (stop)
        # +max_rw_speed -> +32767 (+100%)
        normalized = (speed / self.max_rw_speed) * 32767.0

        # Clamp to int16_t range
        normalized = max(-32767, min(32767, normalized))
        speed_normalized = int(normalized)

        # Pack as int16_t little-endian
        # HID report: [report_id, speed_normalized_low, speed_normalized_high]
        report = struct.pack("<Bh", 0, speed_normalized)

        try:
            device.write(report)
        except (OSError, hid.HIDException):
            # Device disconnected - clear reference (thread-safe)
            with self._reconnect_lock:
                if axis == 'X':
                    self.device_x = None
                elif axis == 'Y':
                    self.device_y = None
                elif axis == 'Z':
                    self.device_z = None
            print(f"Device disconnected: {axis}-axis")

    def set_speed_x(self, speed_rad_s: float):
        """Set X-axis reaction wheel speed (legacy method).

        Deprecated: Use set_speed() instead for multi-axis control.

        Args:
            speed_rad_s: Speed in rad/s (will be normalized to ±100%)
        """
        self._send_to_device(self.device_x, speed_rad_s, 'X')
        self._last_speed[0] = speed_rad_s

    def get_last_speed_x(self) -> float:
        """Get last commanded X-axis speed (rad/s) (legacy method).

        Deprecated: Use get_last_speed() instead.
        """
        return self._last_speed[0]

    def get_last_speed(self) -> NDArray[np.float64]:
        """Get last commanded speeds for all axes (rad/s).

        Returns:
            Array of [wx, wy, wz] in rad/s
        """
        return self._last_speed.copy()

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
