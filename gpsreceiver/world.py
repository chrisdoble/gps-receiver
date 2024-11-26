from __future__ import annotations

import logging
from dataclasses import dataclass

from .subframes import Subframe, Subframe1, Subframe2, Subframe3, Subframe4, Subframe5
from .types import SampleTimestampSeconds, SatelliteId
from .utils import InvariantError, invariant

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

        return SatelliteParameters(self.last_prn_code_trailing_edge_timestamp)


@dataclass
class SatelliteParameters:
    """The information required for satellite calculations.

    These parameters are updated as we receive PRN codes and subframes from the
    satellite. All properties are required which simplifies type checking.
    """

    # The time at which the last PRN code trailing edge was observed.
    last_prn_code_trailing_edge_timestamp: SampleTimestampSeconds

    # The number of PRN code trailing edges that have been observed since the
    # start of the current subframe. Note that this may be negative.
    prn_count: int = 0

    def handle_subframe(self, subframe: Subframe) -> None:
        # Store the TOW count.

        if isinstance(subframe, Subframe1):
            pass
        elif isinstance(subframe, Subframe2):
            pass
        elif isinstance(subframe, Subframe3):
            pass
        elif isinstance(subframe, Subframe4) or isinstance(subframe, Subframe5):
            # We only need the handover word from subframes 4 and 5.
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
