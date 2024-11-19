from .acquirer import Acquisition
from .antenna import OneMsOfSamples
from .pseudosymbol_integrator import PseudosymbolIntegrator
from .tracker import Tracker


class Pipeline:
    """Processes antenna samples to update the world model of a satellite.

    The pipeline is initialised with acquisition parameters and subsequent
    samples pass through: a ``Tracker`` and a ``PseudosymbolIntegrator``.
    """

    def __init__(self, acquisition: Acquisition) -> None:
        self._pseudosymbol_integrator = PseudosymbolIntegrator()
        self._tracker = Tracker(acquisition, self._pseudosymbol_integrator)

    def handle_1ms_of_samples(self, samples: OneMsOfSamples) -> None:
        self._tracker.handle_1ms_of_samples(samples)
