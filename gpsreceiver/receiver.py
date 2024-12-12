import logging
import math

from .acquirer import MainProcessAcquirer
from .antenna import Antenna
from .bit_integrator import UnknownBitPhaseError
from .pipeline import Pipeline
from .subframe_decoder import ParityError
from .types import SatelliteId
from .utils import invariant
from .world import EcefCoordinates, World

logger = logging.getLogger(__name__)


class Receiver:
    def __init__(self, antenna: Antenna) -> None:
        self._acquirer = MainProcessAcquirer()
        self._antenna = antenna
        self._pipelines_by_satellite_id: dict[SatelliteId, Pipeline] = {}
        self._world = World()

    def step_1ms(self) -> None:
        samples = self._antenna.sample_1ms()
        acquisition = self._acquirer.handle_1ms_of_samples(
            samples, set(self._pipelines_by_satellite_id.keys())
        )

        if acquisition is not None:
            invariant(
                acquisition.satellite_id not in self._pipelines_by_satellite_id,
                f"Received acquisition for already tracked satellite {acquisition.satellite_id}",
            )

            logger.info(
                f"[{acquisition.satellite_id}] Acquired:"
                f" carrier_frequency_shift={acquisition.carrier_frequency_shift},"
                f" carrier_phase_shift={acquisition.carrier_phase_shift},"
                f" prn_code_phase_shift={acquisition.prn_code_phase_shift},"
                f" strength={acquisition.strength}"
            )

            self._pipelines_by_satellite_id[acquisition.satellite_id] = Pipeline(
                acquisition, self._world
            )

        for satellite_id, pipeline in list(self._pipelines_by_satellite_id.items()):
            try:
                pipeline.handle_1ms_of_samples(samples)
            except ParityError:
                logger.info(
                    f"[{satellite_id}] Observed parity error, dropping satellite"
                )
                self._drop_satellite(satellite_id)
            except UnknownBitPhaseError:
                logger.info(
                    f"[{satellite_id}] Unable to determine bit phase, dropping satellite"
                )
                self._drop_satellite(satellite_id)

        solution = self._world.compute_solution()
        if solution is not None:
            logger.info(
                f"Found solution: {solution.clock_bias}, {_ecef_to_llh(solution.position)}"
            )

    def _drop_satellite(self, satellite_id: SatelliteId) -> None:
        """Stop tracking a satellite and remove it from the world model.

        This is called when we lose lock on a satellite.
        """

        del self._pipelines_by_satellite_id[satellite_id]
        self._world.drop_satellite(satellite_id)


def _ecef_to_llh(ecef: EcefCoordinates) -> tuple[float, float, float]:
    """Converts ECEF coordinates to latitude, longitude, height coordinates.

    The latitude and longitude are in degrees, the height is in meters.

    Uses Bowring's method[1].

    1: https://en.wikipedia.org/wiki/Geographic_coordinate_conversion#Simple_iterative_conversion_for_latitude_and_height
    """

    # WGS 84 constants.
    a = 6378137.0
    b = 6356752.314245
    e = math.sqrt(1 - (b / a) ** 2)

    # Set h = 0 to get an initial latitude estimate.
    p = math.sqrt(ecef.x**2 + ecef.y**2)
    latitude = math.atan2(ecef.z, p * (1 - e**2))

    # Iteratively calculate latitude.
    for _ in range(5):
        n = a / math.sqrt(1 - (e * math.sin(latitude)) ** 2)
        height = p / math.cos(latitude) - n
        latitude = math.atan2(ecef.z, p * (1 - e**2 * n / (n + height)))

    longitude = math.atan2(ecef.y, ecef.x)

    # Calculate height using the final latitude.
    n = a / math.sqrt(1 - (e * math.sin(latitude)) ** 2)
    height = p / math.cos(latitude) - n

    # Convert to degrees.
    return latitude / math.pi * 180, longitude / math.pi * 180, height
