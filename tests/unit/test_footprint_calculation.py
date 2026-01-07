"""Unit tests for visibility footprint calculation."""

import pytest

from backend.simulation.engine import SimulationEngine


class TestFootprintCalculation:
    """Tests for _calculate_footprint_radius method."""

    @pytest.fixture
    def engine(self):
        """Create simulation engine for testing."""
        return SimulationEngine()

    def test_iss_altitude_5deg_elevation(self, engine):
        """Test footprint at ISS altitude (~400km) with 5 deg min elevation."""
        radius = engine._calculate_footprint_radius(400.0, 5.0)

        # Expected: approximately 18-20 degrees for ISS-like orbit
        # At 400km altitude with 5 deg elevation, footprint should be significant
        assert 15.0 < radius < 25.0, f"Got {radius} degrees"

    def test_geo_altitude_5deg_elevation(self, engine):
        """Test footprint at GEO altitude (~35786km) with 5 deg min elevation."""
        radius = engine._calculate_footprint_radius(35786.0, 5.0)

        # GEO satellite should see almost half the Earth
        # Expected: around 75-80 degrees
        assert 70.0 < radius < 85.0, f"Got {radius} degrees"

    def test_zero_elevation(self, engine):
        """Test footprint with 0 deg elevation (horizon)."""
        radius_0 = engine._calculate_footprint_radius(400.0, 0.0)
        radius_5 = engine._calculate_footprint_radius(400.0, 5.0)

        # 0 deg elevation should give larger footprint than 5 deg
        assert radius_0 > radius_5

    def test_higher_elevation_smaller_footprint(self, engine):
        """Test that higher elevation results in smaller footprint."""
        radius_5 = engine._calculate_footprint_radius(400.0, 5.0)
        radius_10 = engine._calculate_footprint_radius(400.0, 10.0)
        radius_20 = engine._calculate_footprint_radius(400.0, 20.0)

        # Higher elevation angle means smaller visibility footprint
        assert radius_5 > radius_10 > radius_20

    def test_higher_altitude_larger_footprint(self, engine):
        """Test that higher altitude results in larger footprint."""
        radius_200 = engine._calculate_footprint_radius(200.0, 5.0)
        radius_400 = engine._calculate_footprint_radius(400.0, 5.0)
        radius_800 = engine._calculate_footprint_radius(800.0, 5.0)

        # Higher altitude means satellite sees more of Earth
        assert radius_200 < radius_400 < radius_800

    def test_footprint_positive(self, engine):
        """Test that footprint radius is always positive."""
        for altitude in [200, 400, 800, 2000, 35786]:
            for elev in [0, 5, 10, 20, 45]:
                radius = engine._calculate_footprint_radius(float(altitude), float(elev))
                assert radius > 0, f"Negative radius at alt={altitude}km, elev={elev}deg"

    def test_footprint_less_than_90(self, engine):
        """Test that footprint radius never exceeds 90 degrees."""
        # Even at GEO altitude, footprint should be less than 90 degrees
        for altitude in [200, 400, 800, 2000, 35786]:
            radius = engine._calculate_footprint_radius(float(altitude), 0.0)
            assert radius < 90.0, f"Footprint {radius} >= 90 at alt={altitude}km"
