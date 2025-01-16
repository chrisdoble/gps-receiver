"""This module contains types that are used to send data to the HTTP server
    subprocess and are then served by that subprocess to clients."""

from pydantic import BaseModel, Field, field_serializer

from .types import BitPhase, SatelliteId, UtcTimestamp


class GeodeticCoordinates(BaseModel):
    """A location expressed in geodetic coordinates."""

    height: float  # meters
    latitude: float  # degrees
    longitude: float  # degrees


class GeodeticSolution(BaseModel):
    """A computed solution with the position in geodetic coordinates."""

    # See EcefSolution.clock_bias.
    clock_bias: float

    # An estimate of the receiver's position, in geodetic coordinates.
    position: GeodeticCoordinates


class TrackedSatellite(BaseModel):
    """Data regarding a tracked satellite."""

    # When the receiver started tracking the satellite.
    acquired_at: UtcTimestamp

    # Whether the boundary between different bits' pseudosymbols has been found.
    bit_boundary_found: bool

    # The signal's bit phase.
    #
    # ``None`` means we haven't determined it yet.
    bit_phase: BitPhase | None

    # The most recent carrier frequency shift values.
    #
    # The size of this list is determined by ``TRACKING_HISTORY_SIZE``.
    carrier_frequency_shifts: list[float]

    # The most recent correlations of 1 ms of received signal and the prompt
    # local replica. These are used to plot a constellation diagram.
    #
    # The size of this list is determined by ``TRACKING_HISTORY_SIZE``.
    correlations: list[complex]

    # Whether the satellite is healthy.
    #
    # If a satellite is unhealthy it shouldn't be used in solution calculations.
    #
    # May be ``None`` if we haven't received subframe 1 yet.
    is_healthy: bool | None

    # The most recent PRN code phase shift values.
    #
    # The size of this list is determined by ``TRACKING_HISTORY_SIZE``.
    prn_code_phase_shifts: list[float]

    # Whether the subframes required to use this satellite in solution
    # calculations (1, 2, and 3) have been received yet.
    required_subframes_received: bool

    # The satellite's ID.
    satellite_id: SatelliteId

    # The number of subframes that have been decoded from this satellite.
    subframe_count: int

    # Pydantic serialises complex values as strings by default. It's more
    # convenient if they're two-tuples so this field serialiser does that.
    @field_serializer("correlations")
    def serialize_correlations(self, correlations: list[complex]) -> list[list[float]]:
        return [[correlation.real, correlation.imag] for correlation in correlations]


class UntrackedSatellite(BaseModel):
    """Data regarding an untracked satellite."""

    # The time after which the receiver will next try to acquire this satellite.
    next_acquisition_at: UtcTimestamp

    # The satellite's ID.
    satellite_id: SatelliteId


class HttpData(BaseModel):
    """Data sent to the HTTP server subprocess to be served to clients."""

    # The most recently calculated solutions.
    #
    # The size of the list is determined by ``SOLUTION_HISTORY_SIZE``.
    solutions: list[GeodeticSolution]

    # Satellites that are currently being tracked by the receiver.
    tracked_satellites: list[TrackedSatellite]

    # Satellites that aren't currently tracked by the receiver.
    untracked_satellites: list[UntrackedSatellite]
