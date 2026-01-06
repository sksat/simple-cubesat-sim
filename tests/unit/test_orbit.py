"""Tests for SGP4 orbit propagation."""

import pytest
import numpy as np
from backend.dynamics.orbit import OrbitPropagator, OrbitState


class TestOrbitPropagator:
    """Tests for OrbitPropagator class."""

    def test_default_tle_loads(self):
        """Default TLE should load without error."""
        prop = OrbitPropagator()
        assert prop.tle_line1 is not None
        assert prop.tle_line2 is not None

    def test_propagate_returns_orbit_state(self):
        """Propagation should return valid OrbitState."""
        prop = OrbitPropagator()
        state = prop.propagate(0.0)

        assert isinstance(state, OrbitState)
        assert len(state.position_eci) == 3
        assert len(state.velocity_eci) == 3

    def test_position_is_reasonable_altitude(self):
        """Position should be at LEO altitude."""
        prop = OrbitPropagator()
        state = prop.propagate(0.0)

        # Distance from Earth center
        r = np.linalg.norm(state.position_eci)

        # Should be in LEO range (6371 + 200 to 6371 + 2000 km)
        assert 6500 < r < 8500

    def test_velocity_is_reasonable(self):
        """Velocity should be reasonable for LEO."""
        prop = OrbitPropagator()
        state = prop.propagate(0.0)

        # Orbital velocity in LEO is ~7.5 km/s
        v = np.linalg.norm(state.velocity_eci)
        assert 6.5 < v < 8.5

    def test_latitude_in_range(self):
        """Latitude should be in valid range."""
        prop = OrbitPropagator()
        state = prop.propagate(0.0)

        assert -90 <= state.latitude <= 90

    def test_longitude_in_range(self):
        """Longitude should be in valid range."""
        prop = OrbitPropagator()
        state = prop.propagate(0.0)

        assert -180 <= state.longitude <= 180

    def test_altitude_positive(self):
        """Altitude should be positive for valid orbit."""
        prop = OrbitPropagator()
        state = prop.propagate(0.0)

        assert state.altitude > 0

    def test_position_changes_over_time(self):
        """Position should change as time advances."""
        prop = OrbitPropagator()
        state1 = prop.propagate(0.0)
        state2 = prop.propagate(60.0)  # 1 minute later

        # Position should be different
        assert not np.allclose(state1.position_eci, state2.position_eci)

    def test_orbit_period(self):
        """Period should be reasonable for LEO."""
        prop = OrbitPropagator()

        # ISS-like orbit has ~92 minute period
        assert 85 * 60 < prop.period < 120 * 60

    def test_inclination(self):
        """Inclination should be reasonable."""
        prop = OrbitPropagator()

        # Should be between 0 and 180 degrees
        assert 0 <= prop.inclination <= 180

    def test_set_tle_valid(self):
        """Setting valid TLE should work."""
        prop = OrbitPropagator()

        # ISS TLE (known good)
        line1 = "1 25544U 98067A   24001.00000000  .00016717  00000-0  10270-3 0  9003"
        line2 = "2 25544  51.6400   0.0000 0005000   0.0000   0.0000 15.50000000000000"

        prop.set_tle(line1, line2)
        assert prop.tle_line1 == line1
        assert prop.tle_line2 == line2

    def test_set_tle_invalid_raises(self):
        """Setting invalid TLE should raise ValueError."""
        prop = OrbitPropagator()

        with pytest.raises(ValueError):
            prop.set_tle("invalid", "tle")

    def test_latitude_varies_with_inclination(self):
        """Latitude should vary up to inclination over one orbit."""
        prop = OrbitPropagator()
        inc = prop.inclination
        period = prop.period

        # Sample multiple points over one orbit
        latitudes = []
        for i in range(100):
            state = prop.propagate(i * period / 100)
            latitudes.append(state.latitude)

        max_lat = max(latitudes)
        min_lat = min(latitudes)

        # Max latitude should be close to inclination (within 5 degrees)
        # For retrograde orbits (inc > 90), max lat = 180 - inc
        expected_max = inc if inc <= 90 else 180 - inc
        assert abs(max_lat - expected_max) < 5.0
        assert abs(min_lat + expected_max) < 5.0


class TestOrbitStateDataclass:
    """Tests for OrbitState dataclass."""

    def test_orbit_state_fields(self):
        """OrbitState should have all required fields."""
        state = OrbitState(
            position_eci=np.array([7000, 0, 0]),
            velocity_eci=np.array([0, 7.5, 0]),
            latitude=0.0,
            longitude=0.0,
            altitude=628.0,
        )

        assert len(state.position_eci) == 3
        assert len(state.velocity_eci) == 3
        assert state.latitude == 0.0
        assert state.longitude == 0.0
        assert state.altitude == 628.0
