"""Attitude target calculation using main/sub axis concept.

Implements two-axis pointing control where:
- Main axis: Body axis that must point toward main target direction
- Sub axis: Body axis that constrains rotation around main axis
"""

import numpy as np
from numpy.typing import NDArray
from dataclasses import dataclass
from typing import Optional

from backend.dynamics.quaternion import from_dcm, make_dcm_from_two_vectors
from backend.control.target_direction import (
    TargetDirection,
    GroundStation,
    ImagingTarget,
    calculate_target_direction_eci,
)


@dataclass
class PointingConfig:
    """Configuration for two-axis pointing.

    Attributes:
        main_target: Direction for main axis to point toward
        sub_target: Direction for sub axis to point toward
        main_body_axis: Body frame axis to point toward main target
        sub_body_axis: Body frame axis to point toward sub target
        ground_station: Ground station for GROUND_STATION direction
        imaging_target: Target for IMAGING_TARGET direction
    """

    main_target: TargetDirection
    sub_target: TargetDirection
    main_body_axis: NDArray[np.float64]  # Unit vector in body frame
    sub_body_axis: NDArray[np.float64]  # Unit vector in body frame
    ground_station: Optional[GroundStation] = None
    imaging_target: Optional[ImagingTarget] = None

    def __post_init__(self) -> None:
        # Normalize body axes
        self.main_body_axis = np.array(self.main_body_axis, dtype=np.float64)
        self.sub_body_axis = np.array(self.sub_body_axis, dtype=np.float64)
        self.main_body_axis = self.main_body_axis / np.linalg.norm(self.main_body_axis)
        self.sub_body_axis = self.sub_body_axis / np.linalg.norm(self.sub_body_axis)


# Common pointing configurations
def sun_pointing_config() -> PointingConfig:
    """Sun pointing: +Z toward sun, +X toward nadir."""
    return PointingConfig(
        main_target=TargetDirection.SUN,
        sub_target=TargetDirection.EARTH_CENTER,
        main_body_axis=np.array([0.0, 0.0, 1.0]),  # +Z
        sub_body_axis=np.array([1.0, 0.0, 0.0]),  # +X
    )


def nadir_pointing_config() -> PointingConfig:
    """Nadir pointing: -Z toward Earth, +X toward velocity."""
    return PointingConfig(
        main_target=TargetDirection.EARTH_CENTER,
        sub_target=TargetDirection.VELOCITY,
        main_body_axis=np.array([0.0, 0.0, -1.0]),  # -Z
        sub_body_axis=np.array([1.0, 0.0, 0.0]),  # +X
    )


def ground_station_pointing_config(gs: GroundStation) -> PointingConfig:
    """Ground station pointing: -Z toward GS, +X toward velocity."""
    return PointingConfig(
        main_target=TargetDirection.GROUND_STATION,
        sub_target=TargetDirection.VELOCITY,
        main_body_axis=np.array([0.0, 0.0, -1.0]),  # -Z (camera axis)
        sub_body_axis=np.array([1.0, 0.0, 0.0]),  # +X
        ground_station=gs,
    )


def imaging_target_pointing_config(target: ImagingTarget) -> PointingConfig:
    """Imaging target pointing: -Z toward target, +X toward velocity."""
    return PointingConfig(
        main_target=TargetDirection.IMAGING_TARGET,
        sub_target=TargetDirection.VELOCITY,
        main_body_axis=np.array([0.0, 0.0, -1.0]),  # -Z (camera axis)
        sub_body_axis=np.array([1.0, 0.0, 0.0]),  # +X
        imaging_target=target,
    )


def _make_orthogonal(
    vec: NDArray[np.float64],
    ref_vec: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Make vec orthogonal to ref_vec while staying in their plane.

    Uses: orthogonal = (ref × vec) × ref

    Args:
        vec: Vector to orthogonalize
        ref_vec: Reference vector (main direction)

    Returns:
        Unit vector orthogonal to ref_vec in the plane of vec and ref_vec

    Raises:
        ValueError: If vectors are parallel
    """
    cross1 = np.cross(ref_vec, vec)
    cross1_norm = np.linalg.norm(cross1)
    if cross1_norm < 1e-10:
        raise ValueError("Vectors are parallel, cannot orthogonalize")

    result = np.cross(cross1, ref_vec)
    return result / np.linalg.norm(result)


def calculate_target_quaternion(
    config: PointingConfig,
    sat_pos_eci_m: NDArray[np.float64],
    sat_vel_eci_m_s: NDArray[np.float64],
    sun_dir_eci: NDArray[np.float64],
    dcm_eci_to_ecef: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Calculate target quaternion for two-axis pointing.

    Algorithm:
    1. Calculate main target direction in ECI
    2. Calculate sub target direction in ECI
    3. Orthogonalize sub to main (main has priority)
    4. Build DCM from body axes to target directions
    5. Convert to quaternion

    Args:
        config: Pointing configuration
        sat_pos_eci_m: Satellite position in ECI (meters)
        sat_vel_eci_m_s: Satellite velocity in ECI (m/s)
        sun_dir_eci: Sun direction unit vector in ECI
        dcm_eci_to_ecef: DCM from ECI to ECEF

    Returns:
        Target quaternion [x, y, z, w] (ECI to body)

    Raises:
        ValueError: If main and sub directions are parallel
    """
    # Calculate target directions in ECI
    main_dir_eci = calculate_target_direction_eci(
        config.main_target,
        sat_pos_eci_m,
        sat_vel_eci_m_s,
        sun_dir_eci,
        dcm_eci_to_ecef,
        config.ground_station,
        config.imaging_target,
    )

    sub_dir_eci = calculate_target_direction_eci(
        config.sub_target,
        sat_pos_eci_m,
        sat_vel_eci_m_s,
        sun_dir_eci,
        dcm_eci_to_ecef,
        config.ground_station,
        config.imaging_target,
    )

    # Orthogonalize sub direction to main direction
    sub_dir_eci_ortho = _make_orthogonal(sub_dir_eci, main_dir_eci)

    # Build DCM from two vectors
    # make_dcm_from_two_vectors(v1, v2) returns a matrix where rows are the new frame axes
    # So it transforms FROM the original frame TO the new frame
    #
    # dcm_body_to_target: transforms from body frame to target frame
    # Target frame in body coords: X = main_body_axis, Y = ortho(sub_body_axis)
    dcm_body_to_target = make_dcm_from_two_vectors(
        config.main_body_axis,
        config.sub_body_axis,
    )

    # dcm_eci_to_target: transforms from ECI frame to target frame
    # Target frame in ECI coords: X = main_dir_eci, Y = ortho(sub_dir_eci)
    dcm_eci_to_target = make_dcm_from_two_vectors(
        main_dir_eci,
        sub_dir_eci_ortho,
    )

    # To go from ECI to body:
    # v_target = dcm_eci_to_target @ v_eci
    # v_body = dcm_target_to_body @ v_target = (dcm_body_to_target)^T @ v_target
    # So: dcm_eci_to_body = dcm_body_to_target^T @ dcm_eci_to_target
    dcm_eci_to_body = dcm_body_to_target.T @ dcm_eci_to_target

    # Convert to quaternion
    q = from_dcm(dcm_eci_to_body)

    # Ensure positive scalar part
    if q[3] < 0:
        q = -q

    return q


class AttitudeTargetCalculator:
    """Calculator for attitude targets based on pointing configuration."""

    def __init__(self, config: PointingConfig):
        """Initialize calculator.

        Args:
            config: Pointing configuration
        """
        self._config = config

    @property
    def config(self) -> PointingConfig:
        """Current pointing configuration."""
        return self._config

    def set_config(self, config: PointingConfig) -> None:
        """Update pointing configuration.

        Args:
            config: New pointing configuration
        """
        self._config = config

    def set_main_target(
        self,
        direction: TargetDirection,
        body_axis: NDArray[np.float64],
    ) -> None:
        """Set main target direction.

        Args:
            direction: Target direction type
            body_axis: Body axis to point toward target
        """
        self._config.main_target = direction
        self._config.main_body_axis = body_axis / np.linalg.norm(body_axis)

    def set_sub_target(
        self,
        direction: TargetDirection,
        body_axis: NDArray[np.float64],
    ) -> None:
        """Set sub target direction.

        Args:
            direction: Target direction type
            body_axis: Body axis to point toward target
        """
        self._config.sub_target = direction
        self._config.sub_body_axis = body_axis / np.linalg.norm(body_axis)

    def set_ground_station(self, gs: GroundStation) -> None:
        """Set ground station for GROUND_STATION direction."""
        self._config.ground_station = gs

    def set_imaging_target(self, target: ImagingTarget) -> None:
        """Set imaging target for IMAGING_TARGET direction."""
        self._config.imaging_target = target

    def calculate(
        self,
        sat_pos_eci_m: NDArray[np.float64],
        sat_vel_eci_m_s: NDArray[np.float64],
        sun_dir_eci: NDArray[np.float64],
        dcm_eci_to_ecef: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        """Calculate target quaternion.

        Args:
            sat_pos_eci_m: Satellite position in ECI (meters)
            sat_vel_eci_m_s: Satellite velocity in ECI (m/s)
            sun_dir_eci: Sun direction unit vector in ECI
            dcm_eci_to_ecef: DCM from ECI to ECEF

        Returns:
            Target quaternion [x, y, z, w]
        """
        return calculate_target_quaternion(
            self._config,
            sat_pos_eci_m,
            sat_vel_eci_m_s,
            sun_dir_eci,
            dcm_eci_to_ecef,
        )
