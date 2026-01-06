"""Raspberry Pi Pico Reaction Wheel Controller via USB HID.

Controls a physical motor to visualize reaction wheel rotation speed.
Currently supports X-axis only.

HID Protocol:
  Output Report (Host → Pico): [speed_normalized] (int16_t, little-endian)
    - Normalized speed: -32767 = -100%, 0 = stop, +32767 = +100%
    - Pico maps this to motor duty cycle (0-100%)
"""

import struct
from typing import Optional

try:
    import hid
except ImportError:
    hid = None  # type: ignore

# USB VID/PID for Pico RW controller
# Using same as drv8833-motor for now
VID = 0x2E8A
PID = 0x0B33


class PicoRWController:
    """Controls a Raspberry Pi Pico to drive a reaction wheel motor."""

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
        self.device: Optional[hid.Device] = None
        self._last_speed_x: float = 0.0

    def connect(self) -> bool:
        """Attempt to connect to Pico device.

        Returns:
            True if connected, False if device not found
        """
        if self.device is not None:
            return True  # Already connected

        try:
            devices = hid.enumerate(self.vid, self.pid)
            if not devices:
                return False

            self.device = hid.Device(path=devices[0]["path"])
            return True
        except (OSError, hid.HIDException):
            self.device = None
            return False

    def disconnect(self):
        """Disconnect from device."""
        if self.device:
            try:
                self.device.close()
            except Exception:
                pass
            self.device = None

    def is_connected(self) -> bool:
        """Check if device is connected."""
        return self.device is not None

    def set_speed_x(self, speed_rad_s: float):
        """Set X-axis reaction wheel speed.

        Args:
            speed_rad_s: Speed in rad/s (will be normalized to ±100%)
        """
        if self.device is None:
            return  # Silently ignore if not connected

        # Normalize speed to ±100% based on max_rw_speed
        # -max_rw_speed -> -32767 (-100%)
        # 0 -> 0 (stop)
        # +max_rw_speed -> +32767 (+100%)
        normalized = (speed_rad_s / self.max_rw_speed) * 32767.0

        # Clamp to int16_t range
        normalized = max(-32767, min(32767, normalized))
        speed_normalized = int(normalized)

        # Pack as int16_t little-endian
        # HID report: [report_id, speed_normalized_low, speed_normalized_high]
        report = struct.pack("<Bh", 0, speed_normalized)

        try:
            self.device.write(report)
            self._last_speed_x = speed_rad_s
        except (OSError, hid.HIDException):
            # Device disconnected
            self.disconnect()

    def get_last_speed_x(self) -> float:
        """Get last commanded speed (rad/s)."""
        return self._last_speed_x

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
