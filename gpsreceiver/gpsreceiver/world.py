from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np

from .subframes import Subframe, Subframe1, Subframe2, Subframe3, Subframe4, Subframe5
from .types import Bit, SatelliteId, Side, UtcTimestamp
from .utils import InvariantError, invariant, parse_int_from_bits

# Section 3.3.4.
_SECONDS_PER_WEEK: int = 60 * 60 * 24 * 7  # 604,800

# Section 20.3.4.3.
_SPEED_OF_LIGHT: float = 2.99792458e8

logger = logging.getLogger(__name__)


@dataclass(kw_only=True)
class PendingSatelliteParameters:
    """A subset of the information required for satellite calculations.

    After we start tracking a satellite, it takes some time to receive all
    of the information we need to calculate its position and pseudorange. This
    class exists to collect that information until we have it all, at which
    point it can be promoted into the (more type safe) ``SatelliteParameters``.
    """

    prn_code_trailing_edge_timestamp: UtcTimestamp | None = None
    side: Side | None = None
    subframe_1: Subframe1 | None = None
    subframe_2: Subframe2 | None = None
    subframe_3: Subframe3 | None = None
    tow_count: int | None = None

    def handle_subframe(self, subframe: Subframe) -> None:
        self.tow_count = parse_int_from_bits(subframe.handover.tow_count_msbs)

        if isinstance(subframe, Subframe1):
            self.subframe_1 = subframe
        elif isinstance(subframe, Subframe2):
            self.subframe_2 = subframe
        elif isinstance(subframe, Subframe3):
            self.subframe_3 = subframe
        elif isinstance(subframe, Subframe4) or isinstance(subframe, Subframe5):
            # We don't need subframes 4 or 5.
            pass
        else:
            raise InvariantError(f"Unexpected subframe: {subframe}")

    def to_satellite_parameters(self) -> SatelliteParameters | None:
        """Attempt to construct a ``SatelliteParameters`` instance.

        Returns ``None`` if we don't have all the required information yet.
        """

        if (
            self.prn_code_trailing_edge_timestamp is None
            or self.side is None
            or self.subframe_1 is None
            or self.subframe_2 is None
            or self.subframe_3 is None
            or self.tow_count is None
        ):
            return None

        # Multiplications by pi are converting semi-circles to radians.
        return SatelliteParameters(
            a_f0=self.subframe_1.a_f0,
            a_f1=self.subframe_1.a_f1,
            a_f2=self.subframe_1.a_f2,
            c_ic=self.subframe_3.c_ic,
            c_is=self.subframe_3.c_is,
            c_rc=self.subframe_3.c_rc,
            c_rs=self.subframe_2.c_rs,
            c_uc=self.subframe_2.c_uc,
            c_us=self.subframe_2.c_us,
            delta_n=self.subframe_2.delta_n * np.pi,
            e=self.subframe_2.e,
            i_0=self.subframe_3.i_0 * np.pi,
            i_dot=self.subframe_3.i_dot * np.pi,
            m_0=self.subframe_2.m_0 * np.pi,
            omega=self.subframe_3.omega * np.pi,
            omega_0=self.subframe_3.omega_0 * np.pi,
            omega_dot=self.subframe_3.omega_dot * np.pi,
            prn_code_trailing_edge_timestamp=self.prn_code_trailing_edge_timestamp,
            # If the right side is dominant we haven't seen the trailing edge of
            # the previous subframe and we're not yet at the TOW of the next.
            # Setting the PRN count to -1 means that when we increment it to 0
            # in the next millisecond we'll be aligned with the subframe's TOW.
            prn_count=-1 if self.side == Side.RIGHT else 0,
            sqrt_a=self.subframe_2.sqrt_a,
            sv_health=self.subframe_1.sv_health,
            t_gd=self.subframe_1.t_gd,
            t_oc=self.subframe_1.t_oc,
            t_oe=self.subframe_2.t_oe,
            tow_count=self.tow_count,
        )


@dataclass(kw_only=True)
class SatelliteParameters:
    """The information required for satellite calculations.

    These parameters are updated as we receive PRN codes and subframes from the
    satellite. All properties are required which simplifies type checking.
    """

    a_f0: float  # seconds
    a_f1: float  # seconds/second
    a_f2: float  # seconds/second^2
    c_ic: float  # radians
    c_is: float  # radians
    c_rc: float  # meters
    c_rs: float  # meters
    c_uc: float  # radians
    c_us: float  # radians
    delta_n: float  # radians/second
    e: float  # dimensionless
    i_0: float  # radians
    i_dot: float  # radians/second

    m_0: float  # radians
    omega: float  # radians
    omega_0: float  # radians
    omega_dot: float  # radians/second

    # The time at which the last PRN code trailing edge was observed.
    prn_code_trailing_edge_timestamp: UtcTimestamp

    # The number of PRN code trailing edges that have been observed since the
    # start of the current subframe. Note that this may be negative.
    prn_count: int

    sqrt_a: float  # √meters

    # A 6 bit field indicating the health of the satellite's navigation data.
    #
    # See ``Subframe1.sv_health`` for more information.
    sv_health: list[Bit]

    t_gd: float  # seconds
    t_oc: float  # seconds since the start of the GPS week
    t_oe: float  # seconds since the start of the GPS week

    # The time-of-week (TOW) count at the leading edge of the current subframe.
    #
    # The transmitted value is the TOW count at the leading edge of the next
    # subframe. However, this isn't updated until we've parsed a full subframe,
    # so by the time this is set it actually applies to the current subframe.
    #
    # See ``Handover.tow_count_msbs`` for more information.
    tow_count: int

    def handle_subframe(self, subframe: Subframe) -> None:
        # Reset the number of PRN code trailing edges we've observed in the
        # current subframe. It's intentional that we subtract the number of PRN
        # codes per subframe rather than setting it to 0 to handle the cases
        # where, due to Doppler shift, we observe 0 or 2 PRN code trailing edges
        # in a 1 ms period. If we set it to 0 the PRN count would be off by 1
        # which results in an error of ~300 km in the pseudorange.
        self.prn_count -= 6000

        self.tow_count = parse_int_from_bits(subframe.handover.tow_count_msbs)

        # Multiplications by pi are converting semi-circles to radians.
        if isinstance(subframe, Subframe1):
            self.a_f0 = subframe.a_f0
            self.a_f1 = subframe.a_f1
            self.a_f2 = subframe.a_f2
            self.sv_health = subframe.sv_health
            self.t_gd = subframe.t_gd
            self.t_oc = subframe.t_oc
        elif isinstance(subframe, Subframe2):
            self.c_rs = subframe.c_rs
            self.c_uc = subframe.c_uc
            self.c_us = subframe.c_us
            self.delta_n = subframe.delta_n * np.pi
            self.e = subframe.e
            self.m_0 = subframe.m_0 * np.pi
            self.sqrt_a = subframe.sqrt_a
            self.t_oe = subframe.t_oe
        elif isinstance(subframe, Subframe3):
            self.c_ic = subframe.c_ic
            self.c_is = subframe.c_is
            self.c_rc = subframe.c_rc
            self.i_0 = subframe.i_0 * np.pi
            self.i_dot = subframe.i_dot * np.pi
            self.omega = subframe.omega * np.pi
            self.omega_0 = subframe.omega_0 * np.pi
            self.omega_dot = subframe.omega_dot * np.pi
        elif isinstance(subframe, Subframe4) or isinstance(subframe, Subframe5):
            # We don't need anything else from subframes 4 or 5.
            pass
        else:
            raise InvariantError(f"Unexpected subframe: {subframe}")


@dataclass
class EcefCoordinates:
    """A location expressed in Earth-centred, Earth-fixed (ECEF) coordinates."""

    x: float  # meters
    y: float  # meters
    z: float  # meters


@dataclass
class EcefSolution:
    """A computed solution with the position in ECEF coordinates."""

    # An estimate of the receiver's clock bias, in seconds.
    #
    # Note that this is the amount by which the receiver's clock differs from
    # GPS time. For example if it was 1.5 s behind GPS time this would be -1.5.
    clock_bias: float

    # An estimate of the receiver's position, in ECEF coordinates.
    position: EcefCoordinates


class World:
    """Stores satellite parameters and implements solution computation."""

    def __init__(self) -> None:
        # Information about satellites we started tracking recently. Once we
        # have enough information they're promoted to ``_satellite_parameters``
        # and can be used to calculate the receiver's position and pseudorange.
        self._pending_satellite_parameters: dict[
            SatelliteId, PendingSatelliteParameters
        ] = {}

        # Information about satellite's we're tracking.
        self._satellite_parameters: dict[SatelliteId, SatelliteParameters] = {}

    def compute_solution(self) -> EcefSolution | None:
        """Compute the receiver's clock bias and position.

        If that's not possible, returns ``None``.
        """

        # Determine which satellites can be used.
        #
        # In order to be used, a satellite's parameters must be present in
        # ``self._satellite_parameters`` (i.e. we have all of the parameters we
        # need to compute its position and pseudorange), and it must be healthy.
        satellite_ids: list[SatelliteId] = []
        for satellite_id, satellite_parameters in self._satellite_parameters.items():
            if satellite_parameters.sv_health[0] == 0:
                satellite_ids.append(satellite_id)

        # We need at least four satellites to determine the receiver's location.
        if len(satellite_ids) < 4:
            return None

        # Compute the solution using the Gauss-Newton algorithm[1].
        #
        # 1: https://en.wikipedia.org/wiki/Gauss%E2%80%93Newton_algorithm#Description

        # x, y, z, t
        guess = np.zeros(4, dtype=float)

        satellite_positions_and_signal_transit_times = [
            self._compute_satellite_position_and_signal_transit_time(satellite_id)
            for satellite_id in satellite_ids
        ]

        for _ in range(10):
            j = self._compute_jacobian(
                guess, satellite_positions_and_signal_transit_times
            )
            r = self._compute_residuals(
                guess, satellite_positions_and_signal_transit_times
            )
            guess -= np.linalg.inv(j.T @ j) @ j.T @ r

        return EcefSolution(guess[3], EcefCoordinates(*guess[:3]))

    def has_required_subframes(self, satellite_id: SatelliteId) -> bool:
        """Returns whether we have received all the subframes required to use a
        particular satellite in solution calculation (subframes 1, 2, and 3)."""

        return satellite_id in self._satellite_parameters

    def _compute_satellite_position_and_signal_transit_time(
        self, satellite_id: SatelliteId
    ) -> tuple[EcefCoordinates, float]:
        """Computes a satellite's position and the time taken for its signal to
        transit to the receiver."""

        # Table 20-IV.
        t = self._compute_satellite_t(satellite_id)
        sp = self._get_satellite_parameters_or_error(satellite_id)
        t_k = self._wrap_time_delta(t - sp.t_oe)
        e_k = self._compute_satellite_e_k(satellite_id, t_k)
        v_k = 2 * math.atan(math.sqrt((1 + sp.e) / (1 - sp.e)) * math.tan(e_k / 2))
        phi_k = v_k + sp.omega
        delta_u_k = sp.c_us * math.sin(2 * phi_k) + sp.c_uc * math.cos(2 * phi_k)
        delta_r_k = sp.c_rs * math.sin(2 * phi_k) + sp.c_rc * math.cos(2 * phi_k)
        delta_i_k = sp.c_is * math.sin(2 * phi_k) + sp.c_ic * math.cos(2 * phi_k)
        u_k = phi_k + delta_u_k
        r_k = sp.sqrt_a**2 * (1 - sp.e * math.cos(e_k)) + delta_r_k
        i_k = sp.i_0 + delta_i_k + sp.i_dot * t_k
        x_k_prime = r_k * math.cos(u_k)
        y_k_prime = r_k * math.sin(u_k)
        omega_e_dot = 7.2921151467e-5
        omega_k = (
            sp.omega_0 + (sp.omega_dot - omega_e_dot) * t_k - omega_e_dot * sp.t_oe
        )
        x_k = x_k_prime * math.cos(omega_k) - y_k_prime * math.cos(i_k) * math.sin(
            omega_k
        )
        y_k = x_k_prime * math.sin(omega_k) + y_k_prime * math.cos(i_k) * math.cos(
            omega_k
        )
        z_k = y_k_prime * math.sin(i_k)
        position = EcefCoordinates(x_k, y_k, z_k)

        # Calculate the signal transit time.
        #
        # As both are GPS time of week values, we must handle the case where
        # they're in different weeks due week boundaries and wrap the difference
        # appropriately. Note that, due to the receiver's clock bias, it's not
        # always the case that t_rcv > t, i.e. the transit time may be negative!
        t_rcv = self._to_time_of_week(sp.prn_code_trailing_edge_timestamp)
        signal_transit_time = self._wrap_time_delta(t_rcv - t)

        return (position, signal_transit_time)

    def _compute_satellite_t(self, satellite_id: SatelliteId) -> float:
        """Computes the GPS time at which a satellite transmitted the trailing
        edge of its most recently received PRN code (t)."""

        # Section 20.3.3.3.3.1.
        #
        # Page 98 notes that equations 1 and 2 are coupled (to calculate t you
        # need to know delta_t_sv which itself is defined in terms of t). To
        # break this it suggests using t_sv in place of t in equation 2.
        sp = self._get_satellite_parameters_or_error(satellite_id)
        t_sv = sp.tow_count * 6 + sp.prn_count * 0.001
        delta_t = self._wrap_time_delta(t_sv - sp.t_oc)
        f = -4.442807633e-10
        e_k = self._compute_satellite_e_k(
            satellite_id, self._wrap_time_delta(t_sv - sp.t_oe)
        )
        delta_t_r = f * sp.e * sp.sqrt_a * math.sin(e_k)
        delta_t_sv = sp.a_f0 + sp.a_f1 * delta_t + sp.a_f2 * delta_t**2 + delta_t_r

        # Section 20.3.3.3.3.2.
        return t_sv - (delta_t_sv - sp.t_gd)

    def _get_satellite_parameters_or_error(
        self, satellite_id: SatelliteId
    ) -> SatelliteParameters:
        try:
            return self._satellite_parameters[satellite_id]
        except KeyError:
            raise InvariantError(
                f"SatelliteParameters not present for ID: {satellite_id}"
            )

    def _wrap_time_delta(self, t: float) -> float:
        """Accounts for week crossovers by wrapping time deltas.

        ``t`` is the difference between two GPS time of week values, e.g.
        ``t_1 - t_2``. If the difference has a large magnitude that suggests
        one value was at the end of a week and the other at the start. We
        wrap the difference to accurately represent the time between them.
        """

        if t > _SECONDS_PER_WEEK / 2:
            return t - _SECONDS_PER_WEEK
        elif t < -_SECONDS_PER_WEEK / 2:
            return t + _SECONDS_PER_WEEK
        else:
            return t

    def _compute_satellite_e_k(self, satellite_id: SatelliteId, t_k: float) -> float:
        """Computes a satellite's eccentric anomaly (E_k) at a specified number
        of seconds from the ephemeris reference epoch (t_k), in radians.

        Assumes that ``t_k`` has been run through ``_wrap_time_delta``.
        """

        # Table 20-IV.
        mu = 3.986005e14
        sp = self._get_satellite_parameters_or_error(satellite_id)
        a = sp.sqrt_a**2
        n_0 = math.sqrt(mu / a**3)
        n = n_0 + sp.delta_n
        m_k = sp.m_0 + n * t_k
        e = m_k

        # The specification states a minimum of 3 iterations.
        for _ in range(3):
            e += (m_k - e + sp.e * math.sin(e)) / (1 - sp.e * math.cos(e))

        return e

    def _to_time_of_week(self, timestamp: UtcTimestamp) -> float:
        """Converts a UTC timestamp to a GPS time of week.

        This is the number of seconds since the start of the GPS week.
        """

        # GPS doesn't track leap seconds, but UTC does. Thus, we must undo all
        # 18 leap seconds that have occurred since the GPS zero time-point
        # (midnight on the morning of January 6, 1980). Apparently leap seconds
        # will be abandoned by 2035[1] so I'm just going to hard code this.
        #
        # 1: https://en.wikipedia.org/wiki/Leap_second#International_proposals_for_elimination_of_leap_seconds
        leap_seconds = 18
        timestamp += timedelta(seconds=leap_seconds)

        # The GPS time of week is the number of seconds that have occurred since
        # the GPS zero time-point mod the number of seconds in a week.
        #
        # The datetime module doesn't support leap seconds, so this expression
        # is safe, i.e. it doesn't result in leap seconds being counted twice.
        zero = datetime(1980, 1, 6, tzinfo=timezone.utc)
        return (timestamp - zero).total_seconds() % _SECONDS_PER_WEEK

    def _compute_jacobian(
        self,
        guess: np.ndarray,
        satellite_positions_and_signal_transit_times: list[
            tuple[EcefCoordinates, float]
        ],
    ) -> np.ndarray:
        """Computes the Jacobian matrix for the navigation equations.

        Each satellite's pseudorange equation has the form

            sqrt((X - x)^2 + (Y - y)^2 + (Z - z)^2) - c * (T - t) = 0

        where X, Y, and Z are the satellite's coordinates, x, y, and z are an
        estimate of the receiver's coordinates, T is the satellite's signal
        transit time, and t is the receiver's clock bias.
        """
        rows = []
        x, y, z, _ = guess

        for p, _ in satellite_positions_and_signal_transit_times:
            distance = math.sqrt((p.x - x) ** 2 + (p.y - y) ** 2 + (p.z - z) ** 2)
            rows.append(
                [
                    -(p.x - x) / distance,
                    -(p.y - y) / distance,
                    -(p.z - z) / distance,
                    _SPEED_OF_LIGHT,
                ]
            )

        return np.array(rows)

    def _compute_residuals(
        self,
        guess: np.ndarray,
        satellite_positions_and_signal_transit_times: list[
            tuple[EcefCoordinates, float]
        ],
    ) -> np.ndarray:
        """Computes the residual vector for the navigation equations.

        These are the values to be minimised by the Gauss-Newton algorithm.

        See ``_compute_jacobian`` for the pseudorange equation.
        """
        x, y, z, t = guess
        return np.array(
            [
                # The LHS of the pseudorange equation.
                math.sqrt((p.x - x) ** 2 + (p.y - y) ** 2 + (p.z - z) ** 2)
                - _SPEED_OF_LIGHT * (stt - t)
                for p, stt in satellite_positions_and_signal_transit_times
            ]
        )

    def drop_satellite(self, satellite_id: SatelliteId) -> None:
        """Remove a satellite from the world model.

        This is called when we lose lock on a satellite.
        """

        if satellite_id in self._pending_satellite_parameters:
            del self._pending_satellite_parameters[satellite_id]

        if satellite_id in self._satellite_parameters:
            del self._satellite_parameters[satellite_id]

    def handle_prns_tracked(
        self,
        count: int,
        satellite_id: SatelliteId,
        side: Side,
        trailing_edge_timestamp: UtcTimestamp,
    ) -> None:
        """Handle the tracking of one or more PRN codes.

        This required to accurately track time between subframes.

        ``count`` is the number of trailing edges of PRN codes that were
        observed. This will typically be 1, but may also be 0 or 2 if a
        satellite's signal is Doppler shifted as this causes its PRN codes to
        stretch or shrink in time, changing the number of chips per millisecond.

        ``side`` designates which PRN code within the 1 ms chunk of samples
        is dominant. This is required to determine if we've seen the subframe's
        trailing edge when initialising ``SatelliteParameters`` as that affects
        the initial ``prn_count`` and thus the timing. See ``Tracker._side``.

        ``trailing_edge_timestamp`` is the timestamp of the trailing edge of the
        most recently observed PRN code, in receiver time.
        """

        if satellite_id in self._satellite_parameters:
            sp = self._satellite_parameters[satellite_id]
            sp.prn_code_trailing_edge_timestamp = trailing_edge_timestamp
            sp.prn_count += count
        elif satellite_id not in self._pending_satellite_parameters:
            self._pending_satellite_parameters[satellite_id] = (
                PendingSatelliteParameters()
            )

        if satellite_id in self._pending_satellite_parameters:
            # We don't need to track PRN counts for pending parameters because
            # they're always promoted on or 1 ms before the trailing edge of a
            # subframe, i.e. the PRN count is set to either 0 or -1. These two
            # cases are distinguished by the ``side`` parameter.
            #
            # There may be a rare scenario where a satellite has a positive
            # Doppler shift and we happen to see two PRN code trailing edges in
            # the 1 ms period when we receive the trailing edge of the last
            # subframe we need. If that happens the PRN count will permanently
            # be off by 1, i.e. the pseudorange will be off by ~300 km. That
            # seems pretty unlikely though so I'm not going to bother with it.
            psp = self._pending_satellite_parameters[satellite_id]
            psp.prn_code_trailing_edge_timestamp = trailing_edge_timestamp
            psp.side = side
            self._maybe_promote_pending_satellite_parameters(satellite_id)

    def handle_subframe(self, satellite_id: SatelliteId, subframe: Subframe) -> None:
        """Handle a subframe decoded from a satellite's signal."""

        if satellite_id in self._satellite_parameters:
            self._satellite_parameters[satellite_id].handle_subframe(subframe)
        elif satellite_id not in self._pending_satellite_parameters:
            logger.info(f"[{satellite_id}] Created pending parameters")
            self._pending_satellite_parameters[satellite_id] = (
                PendingSatelliteParameters()
            )

        if satellite_id in self._pending_satellite_parameters:
            self._pending_satellite_parameters[satellite_id].handle_subframe(subframe)
            self._maybe_promote_pending_satellite_parameters(satellite_id)

    def _maybe_promote_pending_satellite_parameters(
        self, satellite_id: SatelliteId
    ) -> None:
        """Promote ``PendingSatelliteParameters`` to ``SatelliteParameters`` if
        all the required information is present."""

        invariant(
            satellite_id in self._pending_satellite_parameters,
            "PendingSatelliteParameters not present",
        )
        invariant(
            satellite_id not in self._satellite_parameters,
            "SatelliteParameters already present",
        )

        sp = self._pending_satellite_parameters[satellite_id].to_satellite_parameters()
        if sp is not None:
            logger.info(f"[{satellite_id}] Promoted pending parameters")
            self._satellite_parameters[satellite_id] = sp
            del self._pending_satellite_parameters[satellite_id]
