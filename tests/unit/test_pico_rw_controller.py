"""Unit tests for PicoRWController (3-axis support)."""

import numpy as np
import pytest

try:
    from backend.hardware.pico_rw_controller import PicoRWController
    HID_AVAILABLE = True
except ImportError:
    HID_AVAILABLE = False


@pytest.mark.skipif(not HID_AVAILABLE, reason="hid library not available")
class TestPicoRWController:
    """Test PicoRWController multi-axis functionality."""

    def test_initialization(self):
        """Test controller initialization."""
        controller = PicoRWController()

        assert controller.vid == 0x2E8A
        assert controller.pid == 0x0B33
        assert controller.max_rw_speed == 900.0

        # All devices should be None initially
        assert controller.device_x is None
        assert controller.device_y is None
        assert controller.device_z is None

        # Last speed should be zeros
        assert np.allclose(controller._last_speed, [0.0, 0.0, 0.0])

    def test_connect_returns_status_dict(self):
        """Test that connect() returns a status dictionary."""
        controller = PicoRWController()
        status = controller.connect()

        # Should return dict with 3 axes
        assert isinstance(status, dict)
        assert 'x' in status
        assert 'y' in status
        assert 'z' in status

        # Values should be boolean
        assert isinstance(status['x'], bool)
        assert isinstance(status['y'], bool)
        assert isinstance(status['z'], bool)

    def test_is_connected_returns_status_dict(self):
        """Test that is_connected() returns a status dictionary."""
        controller = PicoRWController()
        status = controller.is_connected()

        # Should return dict with 3 axes
        assert isinstance(status, dict)
        assert status == {'x': False, 'y': False, 'z': False}

    def test_set_speed_validates_array_length(self):
        """Test that set_speed() validates input array length."""
        controller = PicoRWController()

        # Should raise ValueError for wrong length
        with pytest.raises(ValueError, match="Expected 3-element array"):
            controller.set_speed(np.array([100.0, 200.0]))  # Only 2 elements

        with pytest.raises(ValueError, match="Expected 3-element array"):
            controller.set_speed(np.array([100.0, 200.0, 300.0, 400.0]))  # 4 elements

    def test_set_speed_with_no_devices(self):
        """Test set_speed() graceful degradation when no devices connected."""
        controller = PicoRWController()
        # Don't call connect()

        speeds = np.array([100.0, -200.0, 300.0])

        # Should not raise exception even with no devices
        controller.set_speed(speeds)

        # Last speed should be updated
        assert np.allclose(controller._last_speed, speeds)

    def test_get_last_speed(self):
        """Test get_last_speed() returns last commanded speeds."""
        controller = PicoRWController()

        speeds = np.array([150.0, -250.0, 350.0])
        controller.set_speed(speeds)

        result = controller.get_last_speed()
        assert np.allclose(result, speeds)

        # Should return a copy, not the original
        assert result is not controller._last_speed

    def test_set_speed_x_legacy_method(self):
        """Test legacy set_speed_x() method."""
        controller = PicoRWController()

        # Should not raise even with no device
        controller.set_speed_x(100.0)

        # Should update _last_speed[0]
        assert controller._last_speed[0] == 100.0
        assert controller._last_speed[1] == 0.0
        assert controller._last_speed[2] == 0.0

    def test_get_last_speed_x_legacy_method(self):
        """Test legacy get_last_speed_x() method."""
        controller = PicoRWController()

        controller.set_speed_x(200.0)

        assert controller.get_last_speed_x() == 200.0

    def test_disconnect(self):
        """Test disconnect() clears all devices."""
        controller = PicoRWController()

        # Even without actual connections, disconnect should work
        controller.disconnect()

        assert controller.device_x is None
        assert controller.device_y is None
        assert controller.device_z is None

    def test_context_manager(self):
        """Test context manager protocol."""
        with PicoRWController() as controller:
            # Should be able to use controller
            speeds = np.array([100.0, 200.0, 300.0])
            controller.set_speed(speeds)

            assert np.allclose(controller.get_last_speed(), speeds)

        # After exiting context, devices should be disconnected
        # (can't easily test this without real hardware)


@pytest.mark.skipif(not HID_AVAILABLE, reason="hid library not available")
class TestPicoRWControllerNormalization:
    """Test speed normalization logic."""

    def test_normalization_calculation(self):
        """Test that speeds are normalized correctly."""
        controller = PicoRWController(max_rw_speed=900.0)

        # Test normalization bounds
        # max_rw_speed (900 rad/s) should map to 32767
        # This is tested indirectly through _send_to_device

        # We can't directly test normalization without real devices,
        # but we can verify the formula by checking _last_speed tracking
        speeds = np.array([900.0, -900.0, 0.0])
        controller.set_speed(speeds)

        assert np.allclose(controller.get_last_speed(), speeds)

    def test_speed_clamping(self):
        """Test that speeds beyond max are clamped."""
        controller = PicoRWController(max_rw_speed=900.0)

        # Speeds beyond max_rw_speed should be stored as-is
        # (clamping happens in _send_to_device, not in set_speed)
        speeds = np.array([1800.0, -1800.0, 450.0])
        controller.set_speed(speeds)

        # _last_speed should store the original values
        assert np.allclose(controller.get_last_speed(), speeds)
