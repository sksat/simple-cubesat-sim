"""Contact prediction for ground station passes.

Uses step-scan with binary search refinement for efficient contact window detection.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

import numpy as np
from numpy.typing import NDArray

from backend.dynamics.orbit import OrbitPropagator
from backend.control.target_direction import (
    GroundStation,
    calculate_elevation_angle,
)
from backend.prediction.models import ContactWindow
from backend.utils.coordinates import dcm_eci_to_ecef_fast_np


class ContactPredictor:
    """Predicts ground station contact windows.

    Uses a step-scan algorithm with binary search refinement:
    1. Coarse scan (60s steps) to find approximate AOS/LOS
    2. Binary search to refine crossing times to ~1s accuracy
    3. Golden section search to find maximum elevation
    """

    def __init__(
        self,
        orbit_propagator: OrbitPropagator,
        ground_station: GroundStation,
        sim_epoch: datetime,
    ):
        """Initialize contact predictor.

        Args:
            orbit_propagator: Configured orbit propagator
            ground_station: Ground station to predict contacts for
            sim_epoch: Simulation epoch (datetime corresponding to sim_time=0)
        """
        self._orbit_propagator = orbit_propagator
        self._ground_station = ground_station
        self._sim_epoch = sim_epoch

    def predict_next_contact(
        self,
        start_time: float,
        search_duration: float = 6000.0,  # ~100 minutes (1 orbit + margin)
        coarse_step: float = 60.0,
        fine_tolerance: float = 1.0,
    ) -> Optional[ContactWindow]:
        """Find the next contact window after start_time.

        Args:
            start_time: Simulation time to start search (seconds)
            search_duration: How far ahead to search (seconds)
            coarse_step: Step size for initial scan (seconds)
            fine_tolerance: Accuracy for AOS/LOS times (seconds)

        Returns:
            Next ContactWindow or None if no contact within search duration
        """
        end_time = start_time + search_duration

        # Check if currently in contact
        current_visible = self._is_visible(start_time)

        # If already in contact, find LOS first, then next AOS
        if current_visible:
            # Find LOS
            los_time = self._find_crossing(
                start_time, end_time, coarse_step, fine_tolerance, rising=False
            )
            if los_time is None:
                # Contact extends beyond search window - return partial contact
                max_elev, max_elev_time = self._find_max_elevation(
                    start_time, end_time
                )
                return ContactWindow(
                    ground_station_name=self._ground_station.name,
                    start_time=start_time,  # Already in contact
                    end_time=end_time,  # Partial, extends beyond search
                    max_elevation=max_elev,
                    max_elevation_time=max_elev_time,
                )

            # Find next AOS after LOS
            aos_time = self._find_crossing(
                los_time, end_time, coarse_step, fine_tolerance, rising=True
            )
            if aos_time is None:
                # No more contacts in search window - return current contact
                max_elev, max_elev_time = self._find_max_elevation(
                    start_time, los_time
                )
                return ContactWindow(
                    ground_station_name=self._ground_station.name,
                    start_time=start_time,
                    end_time=los_time,
                    max_elevation=max_elev,
                    max_elevation_time=max_elev_time,
                )

            # Find LOS for next contact
            next_los_time = self._find_crossing(
                aos_time, end_time, coarse_step, fine_tolerance, rising=False
            )
            if next_los_time is None:
                next_los_time = end_time  # Partial contact

            max_elev, max_elev_time = self._find_max_elevation(
                aos_time, next_los_time
            )
            return ContactWindow(
                ground_station_name=self._ground_station.name,
                start_time=aos_time,
                end_time=next_los_time,
                max_elevation=max_elev,
                max_elevation_time=max_elev_time,
            )

        # Not in contact - find next AOS
        aos_time = self._find_crossing(
            start_time, end_time, coarse_step, fine_tolerance, rising=True
        )
        if aos_time is None:
            return None  # No contact in search window

        # Find LOS
        los_time = self._find_crossing(
            aos_time, end_time, coarse_step, fine_tolerance, rising=False
        )
        if los_time is None:
            los_time = end_time  # Partial contact extending beyond search window

        # Find maximum elevation
        max_elev, max_elev_time = self._find_max_elevation(aos_time, los_time)

        return ContactWindow(
            ground_station_name=self._ground_station.name,
            start_time=aos_time,
            end_time=los_time,
            max_elevation=max_elev,
            max_elevation_time=max_elev_time,
        )

    def _is_visible(self, sim_time: float) -> bool:
        """Check if ground station is visible at given simulation time."""
        elev = self._get_elevation(sim_time)
        return elev >= self._ground_station.min_elevation_deg

    def _get_elevation(self, sim_time: float) -> float:
        """Get elevation angle at given simulation time.

        Args:
            sim_time: Simulation time in seconds

        Returns:
            Elevation angle in degrees
        """
        # Propagate orbit
        orbit_state = self._orbit_propagator.propagate(sim_time, self._sim_epoch)
        sat_pos_eci_m = np.array(orbit_state.position_eci) * 1000.0  # km to m

        # Get ECI to ECEF rotation
        absolute_time = self._sim_epoch + timedelta(seconds=sim_time)
        dcm_eci_to_ecef = dcm_eci_to_ecef_fast_np(absolute_time)

        # Calculate elevation
        return calculate_elevation_angle(
            sat_pos_eci_m, dcm_eci_to_ecef, self._ground_station
        )

    def _find_crossing(
        self,
        start_time: float,
        end_time: float,
        coarse_step: float,
        fine_tolerance: float,
        rising: bool,
    ) -> Optional[float]:
        """Find visibility crossing (AOS or LOS) using step-scan + binary search.

        Args:
            start_time: Start of search window
            end_time: End of search window
            coarse_step: Step size for initial scan
            fine_tolerance: Target accuracy for crossing time
            rising: True to find AOS (invisible->visible), False for LOS

        Returns:
            Time of crossing or None if not found
        """
        # Coarse scan to find approximate crossing
        prev_time = start_time
        prev_visible = self._is_visible(prev_time)

        t = start_time + coarse_step
        while t <= end_time:
            curr_visible = self._is_visible(t)

            # Check for crossing in desired direction
            if rising and not prev_visible and curr_visible:
                # Found rising edge (AOS)
                return self._binary_search_crossing(
                    prev_time, t, fine_tolerance, rising=True
                )
            elif not rising and prev_visible and not curr_visible:
                # Found falling edge (LOS)
                return self._binary_search_crossing(
                    prev_time, t, fine_tolerance, rising=False
                )

            prev_time = t
            prev_visible = curr_visible
            t += coarse_step

        return None

    def _binary_search_crossing(
        self,
        low_time: float,
        high_time: float,
        tolerance: float,
        rising: bool,
    ) -> float:
        """Binary search to refine crossing time.

        Args:
            low_time: Lower bound (before crossing)
            high_time: Upper bound (after crossing)
            tolerance: Target accuracy
            rising: True for AOS (invisible at low, visible at high)

        Returns:
            Refined crossing time
        """
        while high_time - low_time > tolerance:
            mid_time = (low_time + high_time) / 2
            mid_visible = self._is_visible(mid_time)

            if rising:
                # AOS: looking for invisible->visible
                if mid_visible:
                    high_time = mid_time
                else:
                    low_time = mid_time
            else:
                # LOS: looking for visible->invisible
                if mid_visible:
                    low_time = mid_time
                else:
                    high_time = mid_time

        return (low_time + high_time) / 2

    def _find_max_elevation(
        self,
        start_time: float,
        end_time: float,
        num_samples: int = 20,
    ) -> tuple[float, float]:
        """Find maximum elevation and its time during a contact.

        Uses sampling followed by golden section search for efficiency.

        Args:
            start_time: Contact start time (AOS)
            end_time: Contact end time (LOS)
            num_samples: Number of samples for initial search

        Returns:
            (max_elevation, max_elevation_time) tuple
        """
        # Sample to find approximate maximum
        best_elev = -90.0
        best_time = start_time

        dt = (end_time - start_time) / num_samples
        for i in range(num_samples + 1):
            t = start_time + i * dt
            elev = self._get_elevation(t)
            if elev > best_elev:
                best_elev = elev
                best_time = t

        # Refine with golden section search around best sample
        bracket_size = dt * 2
        low = max(start_time, best_time - bracket_size)
        high = min(end_time, best_time + bracket_size)

        # Golden section search (maximize elevation)
        golden_ratio = (np.sqrt(5) - 1) / 2
        tolerance = 1.0  # 1 second accuracy

        while high - low > tolerance:
            mid1 = high - golden_ratio * (high - low)
            mid2 = low + golden_ratio * (high - low)

            elev1 = self._get_elevation(mid1)
            elev2 = self._get_elevation(mid2)

            if elev1 > elev2:
                high = mid2
            else:
                low = mid1

        final_time = (low + high) / 2
        final_elev = self._get_elevation(final_time)

        return float(final_elev), float(final_time)

    def update_ground_station(self, ground_station: GroundStation) -> None:
        """Update the ground station for predictions.

        Args:
            ground_station: New ground station
        """
        self._ground_station = ground_station

    def update_epoch(self, sim_epoch: datetime) -> None:
        """Update simulation epoch.

        Args:
            sim_epoch: New simulation epoch
        """
        self._sim_epoch = sim_epoch
