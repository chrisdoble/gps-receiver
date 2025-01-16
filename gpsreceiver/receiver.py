import asyncio
import logging
import math
from collections import deque
from dataclasses import dataclass
from multiprocessing import Process, Queue
from queue import Empty
from typing import AsyncGenerator

from aiohttp import web
from pydantic import BaseModel

from .acquirer import Acquirer
from .bit_integrator import UnknownBitPhaseError
from .config import HTTP_UPDATE_INTERVAL_MS, SOLUTION_HISTORY_SIZE
from .http_types import (
    GeodeticCoordinates,
    GeodeticSolution,
    HttpData,
    TrackedSatellite,
    UntrackedSatellite,
)
from .pipeline import Pipeline
from .subframe_decoder import ParityError
from .types import OneMsOfSamples, SatelliteId
from .utils import invariant
from .world import EcefCoordinates, EcefSolution, World

logger = logging.getLogger(__name__)


class Receiver:
    def __init__(self, acquirer: Acquirer) -> None:
        self._acquirer = acquirer

        # Start an HTTP server in a subprocess.
        #
        # The receiver's data is periodically sent to the server via a queue
        # and the server makes it available to clients, e.g. the dashboard.
        self._http_queue: Queue = Queue()
        self._http_subprocess = Process(
            args=(self._http_queue,), daemon=True, target=_run_http_subprocess
        )
        self._http_subprocess.start()

        # The number of ms since data was last sent to the HTTP subprocess.
        self._ms_since_sending_http_data = 0

        self._pipelines_by_satellite_id: dict[SatelliteId, Pipeline] = {}
        self._solutions = deque[GeodeticSolution]([], maxlen=SOLUTION_HISTORY_SIZE)
        self._world = World()

    def handle_1ms_of_samples(self, samples: OneMsOfSamples) -> None:
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
            position = _ecef_to_geodetic(solution.position)
            logger.info(f"Found solution: {solution.clock_bias}, {position}")
            self._solutions.append(
                GeodeticSolution(clock_bias=solution.clock_bias, position=position)
            )

        # Periodically send updated data to the HTTP subprocess.
        self._ms_since_sending_http_data += 1
        if self._ms_since_sending_http_data == HTTP_UPDATE_INTERVAL_MS:
            self._http_queue.put(self._get_http_data())
            self._ms_since_sending_http_data = 0

    def _drop_satellite(self, satellite_id: SatelliteId) -> None:
        """Stop tracking a satellite and remove it from the world model.

        This is called when we lose lock on a satellite.
        """

        del self._pipelines_by_satellite_id[satellite_id]
        self._world.drop_satellite(satellite_id)

    def _get_http_data(self) -> HttpData:
        return HttpData(
            solutions=list(self._solutions),
            tracked_satellites=[
                pipeline.tracked_satellite
                for pipeline in self._pipelines_by_satellite_id.values()
            ],
            untracked_satellites=self._acquirer.untracked_satellites,
        )


def _run_http_subprocess(queue: Queue) -> None:
    data: HttpData | None = None

    async def handler(request: web.Request) -> web.Response:
        return web.Response(
            content_type="application/json",
            text="null" if data is None else data.model_dump_json(),
        )

    async def check_for_data() -> None:
        while True:
            try:
                arg = queue.get(False)
                invariant(
                    isinstance(arg, HttpData),
                    f"Invalid argument sent to HTTP server subprocess: {arg}",
                )

                nonlocal data
                data = arg
            except Empty:
                pass

            await asyncio.sleep(0.001)

    async def data_checker_ctx(app: web.Application) -> AsyncGenerator[None]:
        data_checker = asyncio.create_task(check_for_data())

        yield

        data_checker.cancel()
        await data_checker

    app = web.Application()
    app.add_routes([web.get("/", handler)])
    app.cleanup_ctx.append(data_checker_ctx)
    web.run_app(app, print=lambda x: None)


def _ecef_to_geodetic(ecef: EcefCoordinates) -> GeodeticCoordinates:
    """Converts ECEF coordinates to geodetic coordinates.

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

    return GeodeticCoordinates(
        height=height,
        # Convert to degrees.
        latitude=latitude / math.pi * 180,
        longitude=longitude / math.pi * 180,
    )
