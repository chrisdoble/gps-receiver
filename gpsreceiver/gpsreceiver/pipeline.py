from .acquirer import Acquisition
from .bit_integrator import BitIntegrator
from .http_types import TrackedSatellite
from .pseudosymbol_integrator import PseudosymbolIntegrator
from .subframe_decoder import SubframeDecoder
from .tracker import Tracker
from .types import OneMsOfSamples, UtcTimestamp
from .world import World


class Pipeline:
    """Processes antenna samples to update the world model of a satellite.

    The pipeline is initialised with acquisition parameters and subsequent
    samples pass through: a ``Tracker``, a ``PseudosymbolIntegrator``, a
    ``BitIntegrator``, a ``SubframeDecoder``, and finally to a ``World``.
    """

    def __init__(self, acquisition: Acquisition, world: World) -> None:
        self._acquired_at = acquisition.timestamp
        self._satellite_id = acquisition.satellite_id
        self._subframe_decoder = SubframeDecoder(self._satellite_id, world)
        self._bit_integrator = BitIntegrator(
            acquisition.satellite_id, self._subframe_decoder
        )
        self._pseudosymbol_integrator = PseudosymbolIntegrator(
            self._bit_integrator, acquisition.satellite_id
        )
        self._tracker = Tracker(acquisition, self._pseudosymbol_integrator, world)
        self._world = world

    def handle_1ms_of_samples(self, samples: OneMsOfSamples) -> None:
        self._tracker.handle_1ms_of_samples(samples)

    @property
    def tracked_satellite(self) -> TrackedSatellite:
        return TrackedSatellite(
            acquired_at=self._acquired_at,
            bit_boundary_found=self._pseudosymbol_integrator.bit_boundary_found,
            bit_phase=self._bit_integrator.bit_phase,
            carrier_frequency_shifts=self._tracker.carrier_frequency_shifts,
            correlations=self._tracker.correlations,
            prn_code_phase_shifts=self._tracker.prn_code_phase_shifts,
            required_subframes_received=self._world.has_required_subframes(
                self._satellite_id
            ),
            satellite_id=self._satellite_id,
            subframe_count=self._subframe_decoder.count,
        )
