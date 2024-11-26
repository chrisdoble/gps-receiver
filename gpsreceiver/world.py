from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from .subframes import Subframe, Subframe1, Subframe2, Subframe3, Subframe4, Subframe5
from .types import Bit, SampleTimestampSeconds, SatelliteId
from .utils import InvariantError, invariant, parse_int_from_bits

logger = logging.getLogger(__name__)


@dataclass
class PendingSatelliteParameters:
    """A subset of the information required for satellite calculations.

    After we start tracking a satellite, it takes some time to receive all
    of the information we need to calculate its position and pseudorange. This
    class exists to collect that information until we have it all, at which
    point it can be promoted into the (more type safe) ``SatelliteParameters``.
    """

    last_prn_code_trailing_edge_timestamp: SampleTimestampSeconds | None = None
    subframe_1: Subframe1 | None = None
    subframe_2: Subframe2 | None = None
    subframe_3: Subframe3 | None = None

    def handle_subframe(self, subframe: Subframe) -> None:
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
            self.last_prn_code_trailing_edge_timestamp is None
            or self.subframe_1 is None
            or self.subframe_2 is None
            or self.subframe_3 is None
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
            last_prn_code_trailing_edge_timestamp=self.last_prn_code_trailing_edge_timestamp,
            m_0=self.subframe_2.m_0 * np.pi,
            omega=self.subframe_3.omega * np.pi,
            omega_0=self.subframe_3.omega_0 * np.pi,
            omega_dot=self.subframe_3.omega_dot * np.pi,
            sqrt_a=self.subframe_2.sqrt_a,
            sv_health=self.subframe_1.sv_health,
            t_gd=self.subframe_1.t_gd,
            t_oc=self.subframe_1.t_oc,
            t_oe=self.subframe_2.t_oe,
            tow_count=max(
                parse_int_from_bits(self.subframe_1.handover.tow_count_msbs),
                parse_int_from_bits(self.subframe_2.handover.tow_count_msbs),
                parse_int_from_bits(self.subframe_2.handover.tow_count_msbs),
            ),
            week_number_mod_1024=self.subframe_1.week_number_mod_1024,
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

    # The time at which the last PRN code trailing edge was observed.
    last_prn_code_trailing_edge_timestamp: SampleTimestampSeconds

    m_0: float  # radians
    omega: float  # radians
    omega_0: float  # radians
    omega_dot: float  # radians/second

    sqrt_a: float  # √meters

    # A 6 bit field indicating the health of the satellite's navigation data.
    #
    # See ``Subframe1.sv_health`` for more information.
    sv_health: list[Bit]

    t_gd: float  # seconds
    t_oc: float  # seconds
    t_oe: float  # seconds

    # The time-of-week (TOW) count at the leading edge of the next subframe.
    #
    # See ``Handover.tow_count_msbs`` for more information.
    tow_count: int

    # The GPS week number mod 1024.
    #
    # See ``Subframe1.week_number_mod_1024`` for more information.
    week_number_mod_1024: int

    # The number of PRN code trailing edges that have been observed since the
    # start of the current subframe. Note that this may be negative.
    prn_count: int = 0

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
            self.week_number_mod_1024 = subframe.week_number_mod_1024
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


class World:
    def __init__(self) -> None:
        # Information about satellites we started tracking recently. Once we
        # have enough information they're promoted to ``_satellite_parameters``
        # and can be used to calculate the receiver's position and pseudorange.
        self._pending_satellite_parameters: dict[
            SatelliteId, PendingSatelliteParameters
        ] = {}

        # Information about satellite's we're tracking.
        self._satellite_parameters: dict[SatelliteId, SatelliteParameters] = {}

    def handle_prn_codes(
        self,
        count: int,
        satellite_id: SatelliteId,
        trailing_edge_timestamp: SampleTimestampSeconds,
    ) -> None:
        """Handle observation of the trailing edge of one or more PRN codes.

        This required to accurately track time between subframes.

        ``count`` is the number that were observed. This will typically be 1,
        but it may be 2 if a satellite's Doppler shift is positive as this
        causes its PRN code to shrink in time (we receive more chips per ms).

        ``trailing_edge_timestamp`` is the timestamp of the trailing edge of the
        most recently observed PRN code, in receiver time.
        """

        if satellite_id in self._satellite_parameters:
            sp = self._satellite_parameters[satellite_id]
            sp.last_prn_code_trailing_edge_timestamp = trailing_edge_timestamp
            sp.prn_count += count
        elif satellite_id not in self._pending_satellite_parameters:
            self._pending_satellite_parameters[satellite_id] = (
                PendingSatelliteParameters()
            )

        if satellite_id in self._pending_satellite_parameters:
            # We don't need to track PRN counts for pending parameters. This
            # should work because they're always promoted on the trailing edge
            # of a subframe, i.e. the PRN count will be set to 0 anyway.
            #
            # There may be a rare scenario where a satellite has a positive
            # Doppler shift and we happen to see two PRN code trailing edges in
            # the 1 ms period when we receive the trailing edge of the last
            # subframe we need. If that happens the PRN count will permanently
            # be off by 1, i.e. the pseudorange will be off by ~300 km. That
            # seems pretty unlikely though so I'm not going to bother.
            self._pending_satellite_parameters[
                satellite_id
            ].last_prn_code_trailing_edge_timestamp = trailing_edge_timestamp
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
