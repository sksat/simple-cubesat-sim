"""Tests for attitude target calculation."""

import numpy as np
import pytest
from numpy.testing import assert_allclose

from backend.dynamics.quaternion import (
    from_dcm,
    make_dcm_from_two_vectors,
    to_rotation_matrix,
    rotate_vector,
)
from backend.control.target_direction import (
    TargetDirection,
    GroundStation,
    ImagingTarget,
    MAKINOHARA,
    lla_to_ecef,
    calculate_target_direction_eci,
    calculate_elevation_angle,
)
from backend.control.attitude_target import (
    PointingConfig,
    calculate_target_quaternion,
    sun_pointing_config,
    nadir_pointing_config,
    _make_orthogonal,
)


class TestDCMToQuaternion:
    """Tests for DCM to quaternion conversion."""

    def test_identity(self):
        """Identity DCM converts to identity quaternion."""
        dcm = np.eye(3)
        q = from_dcm(dcm)
        assert_allclose(q, [0, 0, 0, 1], atol=1e-10)

    def test_90deg_rotation_x(self):
        """90 degree rotation about X axis."""
        dcm = np.array([
            [1, 0, 0],
            [0, 0, -1],
            [0, 1, 0],
        ], dtype=np.float64)
        q = from_dcm(dcm)

        # Expected: [sin(45°), 0, 0, cos(45°)]
        expected = np.array([np.sin(np.pi / 4), 0, 0, np.cos(np.pi / 4)])
        assert_allclose(q, expected, atol=1e-10)

    def test_90deg_rotation_z(self):
        """90 degree rotation about Z axis."""
        dcm = np.array([
            [0, -1, 0],
            [1, 0, 0],
            [0, 0, 1],
        ], dtype=np.float64)
        q = from_dcm(dcm)

        # Expected: [0, 0, sin(45°), cos(45°)]
        expected = np.array([0, 0, np.sin(np.pi / 4), np.cos(np.pi / 4)])
        assert_allclose(q, expected, atol=1e-10)

    def test_roundtrip(self):
        """DCM -> quaternion -> DCM should preserve rotation."""
        dcm_original = np.array([
            [0.866, -0.5, 0],
            [0.5, 0.866, 0],
            [0, 0, 1],
        ], dtype=np.float64)
        q = from_dcm(dcm_original)
        dcm_recovered = to_rotation_matrix(q)
        assert_allclose(dcm_recovered, dcm_original, atol=1e-3)


class TestMakeDCMFromTwoVectors:
    """Tests for DCM construction from two vectors."""

    def test_standard_basis(self):
        """X and Y unit vectors produce identity."""
        v1 = np.array([1.0, 0.0, 0.0])
        v2 = np.array([0.0, 1.0, 0.0])
        dcm = make_dcm_from_two_vectors(v1, v2)
        assert_allclose(dcm, np.eye(3), atol=1e-10)

    def test_non_orthogonal_input(self):
        """Non-orthogonal v2 is made orthogonal."""
        v1 = np.array([1.0, 0.0, 0.0])
        v2 = np.array([1.0, 1.0, 0.0])  # 45 degrees from v1
        dcm = make_dcm_from_two_vectors(v1, v2)

        # X axis should be [1, 0, 0]
        assert_allclose(dcm[0], [1, 0, 0], atol=1e-10)
        # Y axis should be [0, 1, 0] (v2 orthogonalized)
        assert_allclose(dcm[1], [0, 1, 0], atol=1e-10)
        # Z axis should be [0, 0, 1]
        assert_allclose(dcm[2], [0, 0, 1], atol=1e-10)

    def test_parallel_vectors_raises(self):
        """Parallel vectors raise ValueError."""
        v1 = np.array([1.0, 0.0, 0.0])
        v2 = np.array([2.0, 0.0, 0.0])
        with pytest.raises(ValueError, match="parallel"):
            make_dcm_from_two_vectors(v1, v2)

    def test_zero_vector_raises(self):
        """Zero vector raises ValueError."""
        v1 = np.array([0.0, 0.0, 0.0])
        v2 = np.array([0.0, 1.0, 0.0])
        with pytest.raises(ValueError, match="zero"):
            make_dcm_from_two_vectors(v1, v2)


class TestMakeOrthogonal:
    """Tests for vector orthogonalization."""

    def test_already_orthogonal(self):
        """Already orthogonal vectors remain unchanged."""
        ref = np.array([1.0, 0.0, 0.0])
        vec = np.array([0.0, 1.0, 0.0])
        result = _make_orthogonal(vec, ref)
        assert_allclose(result, [0, 1, 0], atol=1e-10)

    def test_45_degrees(self):
        """45 degree vector is orthogonalized."""
        ref = np.array([1.0, 0.0, 0.0])
        vec = np.array([1.0, 1.0, 0.0])
        result = _make_orthogonal(vec, ref)
        assert_allclose(result, [0, 1, 0], atol=1e-10)

    def test_parallel_raises(self):
        """Parallel vectors raise ValueError."""
        ref = np.array([1.0, 0.0, 0.0])
        vec = np.array([1.0, 0.0, 0.0])
        with pytest.raises(ValueError, match="parallel"):
            _make_orthogonal(vec, ref)


class TestTargetDirection:
    """Tests for target direction calculation."""

    def test_sun_direction(self):
        """Sun direction returns normalized sun vector."""
        sun_dir = np.array([1.0, 2.0, 3.0])
        result = calculate_target_direction_eci(
            TargetDirection.SUN,
            sat_pos_eci_m=np.array([1e7, 0, 0]),
            sat_vel_eci_m_s=np.array([0, 7000, 0]),
            sun_dir_eci=sun_dir,
            dcm_eci_to_ecef=np.eye(3),
        )
        expected = sun_dir / np.linalg.norm(sun_dir)
        assert_allclose(result, expected, atol=1e-10)

    def test_earth_center(self):
        """Earth center direction is opposite of position."""
        sat_pos = np.array([1e7, 0, 0])
        result = calculate_target_direction_eci(
            TargetDirection.EARTH_CENTER,
            sat_pos_eci_m=sat_pos,
            sat_vel_eci_m_s=np.array([0, 7000, 0]),
            sun_dir_eci=np.array([0, 0, 1]),
            dcm_eci_to_ecef=np.eye(3),
        )
        assert_allclose(result, [-1, 0, 0], atol=1e-10)

    def test_velocity_direction(self):
        """Velocity direction returns normalized velocity."""
        vel = np.array([0, 7000, 0])
        result = calculate_target_direction_eci(
            TargetDirection.VELOCITY,
            sat_pos_eci_m=np.array([1e7, 0, 0]),
            sat_vel_eci_m_s=vel,
            sun_dir_eci=np.array([0, 0, 1]),
            dcm_eci_to_ecef=np.eye(3),
        )
        assert_allclose(result, [0, 1, 0], atol=1e-10)

    def test_orbit_normal(self):
        """Orbit normal is r × v."""
        sat_pos = np.array([1e7, 0, 0])
        sat_vel = np.array([0, 7000, 0])
        result = calculate_target_direction_eci(
            TargetDirection.ORBIT_NORMAL,
            sat_pos_eci_m=sat_pos,
            sat_vel_eci_m_s=sat_vel,
            sun_dir_eci=np.array([0, 0, 1]),
            dcm_eci_to_ecef=np.eye(3),
        )
        # r × v = [0, 0, 7e10] -> normalized [0, 0, 1]
        assert_allclose(result, [0, 0, 1], atol=1e-10)


class TestGroundStation:
    """Tests for ground station functionality."""

    def test_makinohara_coordinates(self):
        """Makinohara ground station has correct coordinates."""
        assert MAKINOHARA.latitude_deg == pytest.approx(34.74)
        assert MAKINOHARA.longitude_deg == pytest.approx(138.22)
        assert MAKINOHARA.min_elevation_deg == pytest.approx(5.0)

    def test_lla_to_ecef_equator(self):
        """Equator point at prime meridian."""
        pos = lla_to_ecef(0, 0, 0)
        # Should be at approximately Earth radius on X axis
        assert pos[0] > 6e6  # About 6378 km
        assert abs(pos[1]) < 1  # Near zero
        assert abs(pos[2]) < 1  # Near zero

    def test_lla_to_ecef_north_pole(self):
        """North pole point."""
        pos = lla_to_ecef(np.pi / 2, 0, 0)
        # Should be at approximately Earth radius on Z axis
        assert abs(pos[0]) < 1
        assert abs(pos[1]) < 1
        assert pos[2] > 6e6  # About 6357 km (polar radius)


class TestAttitudeTargetCalculation:
    """Tests for target quaternion calculation."""

    def test_sun_pointing_basic(self):
        """Basic sun pointing test."""
        config = sun_pointing_config()

        # Satellite at +X, velocity +Y, sun at +Z
        sat_pos = np.array([1e7, 0, 0])
        sat_vel = np.array([0, 7000, 0])
        sun_dir = np.array([0, 0, 1])

        q = calculate_target_quaternion(
            config,
            sat_pos_eci_m=sat_pos,
            sat_vel_eci_m_s=sat_vel,
            sun_dir_eci=sun_dir,
            dcm_eci_to_ecef=np.eye(3),
        )

        # q represents ECI-to-body transformation
        # When a vector in ECI is transformed to body: v_body = R * v_eci
        # The DCM rows are body axes expressed in ECI
        # So rotate_vector(q, v_eci) gives v_body

        # Verify: sun direction in body frame should be +Z body
        sun_in_body = rotate_vector(q, sun_dir)
        assert_allclose(sun_in_body, [0, 0, 1], atol=0.1)

    def test_nadir_pointing_basic(self):
        """Basic nadir pointing test."""
        config = nadir_pointing_config()

        # Satellite at +X, velocity +Y
        sat_pos = np.array([1e7, 0, 0])
        sat_vel = np.array([0, 7000, 0])
        sun_dir = np.array([0, 0, 1])

        q = calculate_target_quaternion(
            config,
            sat_pos_eci_m=sat_pos,
            sat_vel_eci_m_s=sat_vel,
            sun_dir_eci=sun_dir,
            dcm_eci_to_ecef=np.eye(3),
        )

        # q represents ECI-to-body transformation
        # Nadir direction in ECI is -sat_pos/|sat_pos| = [-1, 0, 0]
        nadir_eci = -sat_pos / np.linalg.norm(sat_pos)

        # Verify: nadir in body frame should be -Z body
        nadir_in_body = rotate_vector(q, nadir_eci)
        assert_allclose(nadir_in_body, [0, 0, -1], atol=0.1)

    def test_parallel_targets_raises(self):
        """Parallel main and sub targets raise error."""
        # Both pointing at sun
        config = PointingConfig(
            main_target=TargetDirection.SUN,
            sub_target=TargetDirection.SUN,
            main_body_axis=np.array([0, 0, 1]),
            sub_body_axis=np.array([1, 0, 0]),
        )

        with pytest.raises(ValueError, match="parallel"):
            calculate_target_quaternion(
                config,
                sat_pos_eci_m=np.array([1e7, 0, 0]),
                sat_vel_eci_m_s=np.array([0, 7000, 0]),
                sun_dir_eci=np.array([0, 0, 1]),
                dcm_eci_to_ecef=np.eye(3),
            )


class TestElevationAngle:
    """Tests for elevation angle calculation."""

    def test_satellite_at_zenith(self):
        """Satellite directly above should have 90 degree elevation."""
        # Ground station at equator, prime meridian
        gs = GroundStation("Test", 0, 0)

        # Satellite directly above (high altitude on X axis in ECEF)
        sat_pos_eci = np.array([1e8, 0, 0])  # 100,000 km altitude
        dcm_eci_to_ecef = np.eye(3)

        elev = calculate_elevation_angle(sat_pos_eci, dcm_eci_to_ecef, gs)
        assert elev == pytest.approx(90, abs=5)  # Close to zenith

    def test_satellite_below_horizon(self):
        """Satellite on opposite side of Earth has negative elevation."""
        # Ground station at equator, prime meridian
        gs = GroundStation("Test", 0, 0)

        # Satellite on opposite side of Earth
        sat_pos_eci = np.array([-1e8, 0, 0])
        dcm_eci_to_ecef = np.eye(3)

        elev = calculate_elevation_angle(sat_pos_eci, dcm_eci_to_ecef, gs)
        assert elev < 0
