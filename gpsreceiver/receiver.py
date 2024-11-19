import pprint

from .acquirer import Acquirer
from .antenna import Antenna
from .pipeline import Pipeline
from .types import SatelliteId


class Receiver:
    def __init__(self, antenna: Antenna) -> None:
        self._acquirer = Acquirer()
        self._antenna = antenna
        self._pipelines_by_satellite_id: dict[SatelliteId, Pipeline] = {}

    def step_1ms(self) -> None:
        samples = self._antenna.sample_1ms()
        acquisitions = self._acquirer.handle_1ms_of_samples(
            samples, set(self._pipelines_by_satellite_id.keys())
        )

        for acquisition in acquisitions:
            assert (
                acquisition.satellite_id not in self._pipelines_by_satellite_id
            ), f"Received acquisition for already tracked satellite {acquisition.satellite_id}"
            self._pipelines_by_satellite_id[acquisition.satellite_id] = Pipeline(
                acquisition
            )

        for pipeline in self._pipelines_by_satellite_id.values():
            pipeline.handle_1ms_of_samples(samples)
