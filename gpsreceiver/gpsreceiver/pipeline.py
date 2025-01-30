from .acquirer import Acquisition
from .http_types import TrackedSatellite
from .pseudobit_integrator import PseudobitIntegrator
from .pseudosymbol_integrator import PseudosymbolIntegrator
from .subframe_decoder import SubframeDecoder
from .tracker import Tracker
from .types import OneMsOfSamples, UtcTimestamp
from .world import World


class Pipeline:
    """Processes antenna samples to update the world model of a satellite.

    The pipeline is initialised with acquisition parameters and subsequent
    samples pass through: a ``Tracker``, a ``PseudosymbolIntegrator``, a
    ``PseudobitIntegrator``, a ``SubframeDecoder``, and finally to a ``World``.
    """

    def __init__(self, acquisition: Acquisition, world: World) -> None:
        self._acquired_at = acquisition.timestamp
        self._satellite_id = acquisition.satellite_id
        self._subframe_decoder = SubframeDecoder(self._satellite_id, world)
        self._pseudobit_integrator = PseudobitIntegrator(
            acquisition.satellite_id, self._subframe_decoder
        )
        self._pseudosymbol_integrator = PseudosymbolIntegrator(
            self._pseudobit_integrator, acquisition.satellite_id
        )
        self._tracker = Tracker(acquisition, self._pseudosymbol_integrator, world)
        self._world = world

    def get_tracked_satellite(self, time: UtcTimestamp) -> TrackedSatellite:
        return TrackedSatellite(
            bit_boundary_found=self._pseudosymbol_integrator.bit_boundary_found,
            bit_phase=self._pseudobit_integrator.bit_phase,
            carrier_frequency_shifts=self._tracker.carrier_frequency_shifts,
            correlations=self._tracker.correlations,
            duration=(time - self._acquired_at).total_seconds(),
            prn_code_phase_shifts=self._tracker.prn_code_phase_shifts,
            required_subframes_received=self._world.has_required_subframes(
                self._satellite_id
            ),
            satellite_id=self._satellite_id,
            subframe_count=self._subframe_decoder.count,
        )

    def handle_1ms_of_samples(self, samples: OneMsOfSamples) -> None:
        self._tracker.handle_1ms_of_samples(samples)
