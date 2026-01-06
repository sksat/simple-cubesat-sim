"""Tests for coordinate transformation utilities."""

import pytest
import numpy as np
from datetime import datetime, timezone
from astropy.time import Time
from backend.utils.coordinates import (
    geodetic_to_ecef,
    ecef_to_threejs,
    geodetic_to_threejs,
    get_sun_direction_ecef,
    get_sun_direction_threejs,
    gmst_from_datetime,
    dcm_eci_to_ecef_fast_np,
    EARTH_RADIUS_KM,
)


class TestGeodeticToECEF:
    """Tests for geodetic_to_ecef function."""

    def test_equator_prime_meridian(self):
        """Point on equator at prime meridian should be on +X axis."""
        x, y, z = geodetic_to_ecef(lat_deg=0, lon_deg=0, alt_km=0)
        # Should be approximately (R_earth, 0, 0)
        assert x > 6370  # Close to Earth radius
        assert abs(y) < 1  # Near zero
        assert abs(z) < 1  # Near zero

    def test_equator_90_east(self):
        """Point on equator at 90°E should be on +Y axis."""
        x, y, z = geodetic_to_ecef(lat_deg=0, lon_deg=90, alt_km=0)
        # Should be approximately (0, R_earth, 0)
        assert abs(x) < 1
        assert y > 6370
        assert abs(z) < 1

    def test_north_pole(self):
        """North pole should be on +Z axis."""
        x, y, z = geodetic_to_ecef(lat_deg=90, lon_deg=0, alt_km=0)
        # Should be approximately (0, 0, R_earth)
        assert abs(x) < 1
        assert abs(y) < 1
        assert z > 6350  # Slightly less due to Earth flattening

    def test_altitude_increases_distance(self):
        """Higher altitude should increase distance from Earth center."""
        x0, y0, z0 = geodetic_to_ecef(lat_deg=0, lon_deg=0, alt_km=0)
        x1, y1, z1 = geodetic_to_ecef(lat_deg=0, lon_deg=0, alt_km=400)

        r0 = (x0**2 + y0**2 + z0**2) ** 0.5
        r1 = (x1**2 + y1**2 + z1**2) ** 0.5

        assert r1 > r0
        assert abs(r1 - r0 - 400) < 1  # Should increase by ~400 km


class TestECEFToThreejs:
    """Tests for ecef_to_threejs function."""

    def test_north_pole_is_up(self):
        """ECEF Z (North) should map to Three.js Y (up)."""
        # Point at North Pole in ECEF
        x, y, z = ecef_to_threejs(0, 0, EARTH_RADIUS_KM)
        # Should be at (0, 1, 0) in Three.js
        assert abs(x) < 0.01
        assert abs(y - 1.0) < 0.01
        assert abs(z) < 0.01

    def test_prime_meridian_is_scene_x(self):
        """ECEF X (prime meridian) should map to Three.js X."""
        x, y, z = ecef_to_threejs(EARTH_RADIUS_KM, 0, 0)
        # Should be at (1, 0, 0) in Three.js
        assert abs(x - 1.0) < 0.01
        assert abs(y) < 0.01
        assert abs(z) < 0.01

    def test_90_east_is_scene_z(self):
        """ECEF Y (90°E) should map to Three.js Z."""
        x, y, z = ecef_to_threejs(0, EARTH_RADIUS_KM, 0)
        # Should be at (0, 0, 1) in Three.js
        assert abs(x) < 0.01
        assert abs(y) < 0.01
        assert abs(z - 1.0) < 0.01


class TestGeodeticToThreejs:
    """Tests for geodetic_to_threejs function (combined conversion)."""

    def test_equator_prime_meridian(self):
        """Equator at prime meridian should be at Scene +X."""
        x, y, z = geodetic_to_threejs(lat_deg=0, lon_deg=0, alt_km=0)
        # Should be approximately (1, 0, 0)
        assert x > 0.99
        assert abs(y) < 0.01
        assert abs(z) < 0.01

    def test_north_pole(self):
        """North pole should be at Scene +Y (up)."""
        x, y, z = geodetic_to_threejs(lat_deg=90, lon_deg=0, alt_km=0)
        # Should be approximately (0, 1, 0)
        assert abs(x) < 0.01
        assert y > 0.99  # Slightly less than 1 due to Earth flattening
        assert abs(z) < 0.01

    def test_equator_90_east(self):
        """Equator at 90°E should be at Scene +Z."""
        x, y, z = geodetic_to_threejs(lat_deg=0, lon_deg=90, alt_km=0)
        # Should be approximately (0, 0, 1)
        assert abs(x) < 0.01
        assert abs(y) < 0.01
        assert z > 0.99

    def test_orbital_altitude(self):
        """600km orbit altitude should give radius > 1."""
        x, y, z = geodetic_to_threejs(lat_deg=0, lon_deg=0, alt_km=600)
        r = (x**2 + y**2 + z**2) ** 0.5
        # 6371 + 600 = 6971 km, normalized: 6971/6371 ≈ 1.094
        assert 1.09 < r < 1.10

    def test_sso_inclination_latitude(self):
        """Test position at high latitude typical for SSO."""
        x, y, z = geodetic_to_threejs(lat_deg=80, lon_deg=45, alt_km=600)
        r = (x**2 + y**2 + z**2) ** 0.5
        # Should be at orbital radius
        assert 1.09 < r < 1.10
        # Y should be large (high latitude)
        assert y > 0.9


class TestSunDirection:
    """Tests for sun direction functions."""

    def test_sun_direction_ecef_is_unit_vector(self):
        """Sun direction should be a unit vector."""
        x, y, z = get_sun_direction_ecef()
        r = (x**2 + y**2 + z**2) ** 0.5
        assert abs(r - 1.0) < 0.001

    def test_sun_direction_threejs_is_unit_vector(self):
        """Sun direction in Three.js should be a unit vector."""
        x, y, z = get_sun_direction_threejs()
        r = (x**2 + y**2 + z**2) ** 0.5
        assert abs(r - 1.0) < 0.001

    def test_sun_direction_with_specific_time(self):
        """Sun direction should work with a specific time."""
        # Summer solstice 2024 - sun should be in northern hemisphere
        time = Time("2024-06-21T12:00:00", scale="utc")
        x, y, z = get_sun_direction_ecef(time)
        r = (x**2 + y**2 + z**2) ** 0.5
        assert abs(r - 1.0) < 0.001
        # Sun should be above equatorial plane (z > 0) at summer solstice
        assert z > 0

    def test_sun_direction_coordinate_mapping(self):
        """ECEF to Three.js sun direction mapping should be consistent."""
        time = Time("2024-03-20T12:00:00", scale="utc")
        ecef_x, ecef_y, ecef_z = get_sun_direction_ecef(time)
        three_x, three_y, three_z = get_sun_direction_threejs(time)

        # Verify mapping: Scene X = ECEF X, Scene Y = ECEF Z, Scene Z = ECEF Y
        assert abs(three_x - ecef_x) < 0.001
        assert abs(three_y - ecef_z) < 0.001
        assert abs(three_z - ecef_y) < 0.001


class TestGMST:
    """Tests for GMST (Greenwich Mean Sidereal Time) functions."""

    def test_gmst_matches_astropy(self):
        """GMST should match Astropy's calculation within 0.01 degrees."""
        dt = datetime(2026, 1, 6, 12, 0, 0, tzinfo=timezone.utc)

        # Our fast implementation
        gmst_fast = np.degrees(gmst_from_datetime(dt))

        # Astropy reference
        from astropy.coordinates import EarthLocation
        time = Time(dt)
        gmst_astropy = time.sidereal_time('mean', 'greenwich').deg

        # Should match within 0.01 degrees
        diff = abs(gmst_fast - gmst_astropy)
        if diff > 180:
            diff = 360 - diff
        assert diff < 0.01, f"GMST diff: {diff}°"

    def test_gmst_increases_with_time(self):
        """GMST should increase by ~360° per sidereal day."""
        dt1 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        dt2 = datetime(2026, 1, 1, 6, 0, 0, tzinfo=timezone.utc)

        gmst1 = np.degrees(gmst_from_datetime(dt1))
        gmst2 = np.degrees(gmst_from_datetime(dt2))

        # 6 hours should be ~90 degrees
        diff = (gmst2 - gmst1) % 360
        assert 89 < diff < 91, f"Expected ~90° for 6 hours, got {diff}°"

    def test_dcm_is_rotation_matrix(self):
        """DCM should be a proper rotation matrix (orthogonal, det=1)."""
        dt = datetime(2026, 1, 6, 12, 0, 0, tzinfo=timezone.utc)
        dcm = dcm_eci_to_ecef_fast_np(dt)

        # Check orthogonality: R^T @ R = I
        identity = dcm.T @ dcm
        assert np.allclose(identity, np.eye(3), atol=1e-10)

        # Check determinant = 1
        det = np.linalg.det(dcm)
        assert abs(det - 1.0) < 1e-10

    def test_dcm_z_axis_unchanged(self):
        """Z-axis should be unchanged by ECI-to-ECEF rotation."""
        dt = datetime(2026, 1, 6, 12, 0, 0, tzinfo=timezone.utc)
        dcm = dcm_eci_to_ecef_fast_np(dt)

        z_eci = np.array([0, 0, 1])
        z_ecef = dcm @ z_eci

        # Z should be unchanged (rotation is around Z)
        assert np.allclose(z_ecef, z_eci, atol=1e-10)

    def test_dcm_rotates_xy_plane(self):
        """ECI X and Y should be rotated in the XY plane."""
        dt = datetime(2026, 1, 6, 12, 0, 0, tzinfo=timezone.utc)
        dcm = dcm_eci_to_ecef_fast_np(dt)

        x_eci = np.array([1, 0, 0])
        y_eci = np.array([0, 1, 0])

        x_ecef = dcm @ x_eci
        y_ecef = dcm @ y_eci

        # X should stay in XY plane (z=0)
        assert abs(x_ecef[2]) < 1e-10
        # Y should stay in XY plane (z=0)
        assert abs(y_ecef[2]) < 1e-10
        # Magnitudes should be preserved
        assert np.allclose(np.linalg.norm(x_ecef), 1.0)
        assert np.allclose(np.linalg.norm(y_ecef), 1.0)
