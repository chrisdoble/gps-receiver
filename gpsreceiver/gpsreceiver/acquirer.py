import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from datetime import MINYEAR, datetime, timedelta, timezone
from multiprocessing import Pipe, Process
from multiprocessing.connection import Connection
from typing import cast

import numpy as np

from .config import (
    ACQUISITION_INTERVAL,
    ACQUISITION_STRENGTH_THRESHOLD,
    ALL_SATELLITE_IDS,
    MS_OF_SAMPLES_REQUIRED_TO_PERFORM_ACQUISITION,
    SAMPLES_PER_MILLISECOND,
)
from .constants import SAMPLE_TIMES, SAMPLES_PER_SECOND
from .http_types import UntrackedSatellite
from .prn_codes import COMPLEX_UPSAMPLED_PRN_CODES_BY_SATELLITE_ID
from .types import OneMsOfSamples, SatelliteId, UtcTimestamp
from .utils import InvariantError, invariant


@dataclass(kw_only=True)
class Acquisition:
    """The parameters resulting from acquisition of a GPS satellite signal.

    Note that the frequency/phase shift parameters are the observed shifts, i.e.
    we must negate them on a received signal to perform carrier wipeoff.
    """

    # An estimate of the carrier signal's frequency shift in Hz.
    carrier_frequency_shift: float

    # An estimate of the carrier signal's phase shift in radians.
    #
    # This can be inaccurate if we encountered a navigation bit change during
    # acquisition, but the Costas loop in the tracking phase should fix it.
    carrier_phase_shift: float

    # An estimate of the C/A PRN code's phase shift in half-chips.
    #
    # This will be in the range [0, 2045].
    prn_code_phase_shift: int

    # The ID of the GPS satellite whose signal was acquired.
    satellite_id: SatelliteId

    # The strength of the acquisition.
    #
    # This is the peak-to-mean ratio of the signal correlations for this
    # particular Doppler shift and all possible C/A PRN code phase shifts.
    strength: float

    # When the acquisition occurred.
    timestamp: UtcTimestamp


class Acquirer(ABC):
    """Detects GPS satellite signals and determines their parameters.

    This is abstract so subclasses can decide how to schedule computations, e.g.
    whether they should block the main process or occur in a subprocess.
    """

    def __init__(self) -> None:
        # When to next attempt acquisition for each satellite, in receiver time.
        #
        # Set to the minimum value so we perform acquisition on startup.
        self._next_acquisition_at_by_satellite_id: dict[SatelliteId, UtcTimestamp] = {
            i: datetime(MINYEAR, 1, 1, tzinfo=timezone.utc) for i in ALL_SATELLITE_IDS
        }

        # The most recently received samples.
        self._samples = deque[OneMsOfSamples](
            maxlen=MS_OF_SAMPLES_REQUIRED_TO_PERFORM_ACQUISITION
        )

        # The most recently received set of tracked satellite IDs.
        self._tracked_satellite_ids: set[SatelliteId] = set()

    def handle_1ms_of_samples(
        self, samples: OneMsOfSamples, tracked_satellite_ids: set[SatelliteId]
    ) -> Acquisition | None:
        """Handles 1 ms of samples.

        Returns an ``Acquisition`` if a satellite's signal has been acquired.
        """

        self._samples.append(samples)
        self._tracked_satellite_ids = tracked_satellite_ids

        # Check if we have enough samples to perform acquisition.
        if len(self._samples) < MS_OF_SAMPLES_REQUIRED_TO_PERFORM_ACQUISITION:
            return None

        acquisition = self._get_acquisition()
        if acquisition is not None:
            self._next_acquisition_at_by_satellite_id[acquisition.satellite_id] = (
                samples.end_timestamp + ACQUISITION_INTERVAL
            )

            if acquisition.strength >= ACQUISITION_STRENGTH_THRESHOLD:
                return acquisition

        return None

    @property
    def untracked_satellites(self) -> list[UntrackedSatellite]:
        return [
            UntrackedSatellite(
                next_acquisition_at=next_acquisition_at,
                satellite_id=satellite_id,
            )
            for satellite_id, next_acquisition_at in self._next_acquisition_at_by_satellite_id.items()
            if satellite_id not in self._tracked_satellite_ids
        ]

    @abstractmethod
    def _get_acquisition(self) -> Acquisition | None:
        """Returns an ``Acquisition``, if one is ready."""

        pass

    def _get_next_acquisition_target(self) -> SatelliteId | None:
        """Determines which satellite we should attempt to acquire next."""

        now = self._samples[-1].end_timestamp
        untracked_satellite_ids = ALL_SATELLITE_IDS - self._tracked_satellite_ids
        candidates = [
            (si, t)
            for si, t in self._next_acquisition_at_by_satellite_id.items()
            if si in untracked_satellite_ids and t <= now
        ]
        candidates.sort(key=lambda c: c[1])

        if len(candidates) > 0:
            return candidates[0][0]

        return None


class MainProcessAcquirer(Acquirer):
    """An ``Acquirer`` that performs computations in the main process.

    To be used when sampling a recorded signal, otherwise the receiver churns
    through all of the recorded samples before acquisition is complete.
    """

    def _get_acquisition(self) -> Acquisition | None:
        satellite_id = self._get_next_acquisition_target()
        if satellite_id is not None:
            return _acquire_satellite(list(self._samples), satellite_id)

        return None


class SubprocessAcquirer(Acquirer):
    """An ``Acquirer`` that performs computations in a subprocess.

    To be used when sampling a real-time signal, otherwise there will be periods
    where we don't sample because the computations block the main process.
    """

    def __init__(self) -> None:
        super().__init__()

        # The connections through which the processes communicate.
        self._connection, connection = Pipe()

        # The subprocess.
        #
        # Marked as a daemon so it's killed alongside the main process.
        self._subprocess = Process(
            args=(connection,),
            daemon=True,
            target=_run_subprocess,
        )
        self._subprocess.start()

        # Whether we're waiting for the subprocess to return an ``Acquisition``.
        self._waiting = False

    def _get_acquisition(self) -> Acquisition | None:
        invariant(self._subprocess.is_alive(), "Acquisition subprocess has terminated")

        if self._waiting:
            if self._connection.poll():
                result = self._connection.recv()
                invariant(
                    isinstance(result, Acquisition),
                    f"Invalid value received from acquisition subprocess: {result}",
                )
                self._waiting = False
                return result
        else:
            satellite_id = self._get_next_acquisition_target()
            if satellite_id is not None:
                self._connection.send((list(self._samples), satellite_id))
                self._waiting = True

        return None


def _run_subprocess(connection: Connection) -> None:
    while True:
        # If we haven't received any arguments from the main process, sleep.
        if not connection.poll():
            time.sleep(0.001)
            continue

        args = connection.recv()
        invariant(
            isinstance(args, tuple) and len(args) == 2,
            f"Invalid arguments sent to acquisition subprocess: {args}",
        )

        samples, satellite_id = args
        invariant(
            isinstance(samples, list)
            and all([isinstance(s, OneMsOfSamples) for s in samples]),
            f"Invalid samples sent to acquisition subprocess: {samples}",
        )
        invariant(
            isinstance(satellite_id, int),
            f"Invalid satellite ID send to acquisition subprocess: {satellite_id}",
        )

        connection.send(_acquire_satellite(samples, satellite_id))


def _acquire_satellite(
    samples: list[OneMsOfSamples], satellite_id: SatelliteId
) -> Acquisition:
    """Attempts to acquire the signal of a particular GPS satellite."""

    # The following attempts to acquire the satellite's signal at a fixed
    # number of frequency shifts in a range around a central value. The
    # central value is updated to be the frequency shift of the strongest
    # candidate, the range is reduced, and the process is repeated until
    # we're searching a continuous range. This means we start by searching a
    # large range and gradually narrow down on the most promising regions.
    #
    # The initial central value is 0 and the initial frequency shift range
    # is ±7.680 kHz. This range was chosen to accommodate all reasonable
    # receiver and satellite motion, receiver oscillation variance, etc. On
    # each iteration the range is split into 31 equally-spaced values
    # (including endpoints) and is reduced by a factor of two. This means on
    # the first iteration the step size is 512 Hz, the second it's 256 Hz,
    # etc., until the tenth iteration where it's 1 Hz and we're searching a
    # continuous range. At that point we've found the strongest candidate.
    best_acquisition: Acquisition | None = None
    centre_frequency_shift: float = 0
    half_frequency_shift_range: float = 7_680

    while half_frequency_shift_range >= 15:
        new_acquisition = _acquire_satellite_at_frequency_shifts(
            np.linspace(
                centre_frequency_shift - half_frequency_shift_range,
                centre_frequency_shift + half_frequency_shift_range,
                31,
            ),
            samples,
            satellite_id,
        )

        if (
            best_acquisition is None
            or new_acquisition.strength > best_acquisition.strength
        ):
            best_acquisition = new_acquisition

        centre_frequency_shift = best_acquisition.carrier_frequency_shift
        half_frequency_shift_range /= 2

    if best_acquisition is None:
        raise InvariantError("Missing acquisition result")

    return best_acquisition


def _acquire_satellite_at_frequency_shifts(
    frequency_shifts: np.ndarray,
    samples: list[OneMsOfSamples],
    satellite_id: SatelliteId,
) -> Acquisition:
    """Attempts to acquire the signal of a particular GPS satellite at
    particular frequency shifts.

    Returns the best acquisition result regardless of whether its strength
    exceeds the acquisition strength threshold.
    """

    # For each frequency shift we perform both coherent and non-coherent
    # integration for every 1 ms period of samples and add the results. This
    # strengthens weak signals as if the 1 ms period were extended, but
    # minimises the issue of navigation bit changes affecting the magnitude
    # of the correlation. We then find the frequency shift and PRN code
    # phase that give the greatest non-coherent sum - this is the strongest
    # signal. The argument of the corresponding coherent sum is an estimate
    # of the phase of the carrier wave. Finally, the peak-to-mean ratio of
    # all correlations for the strongest frequency shift gives the strength.

    prn_code = COMPLEX_UPSAMPLED_PRN_CODES_BY_SATELLITE_ID[satellite_id]
    prn_code_fft_conj = np.conj(np.fft.fft(prn_code))

    coherent_sums = np.zeros((len(frequency_shifts), len(prn_code)), dtype=complex)
    magnitude_sums = np.zeros((len(frequency_shifts), len(prn_code)))

    for i, f in enumerate(frequency_shifts):
        for j, samples_i in enumerate(samples):
            # Perform carrier wipeoff.
            shifted_samples = samples_i.samples * np.exp(
                -2j * np.pi * f * (SAMPLE_TIMES + j * 0.001)
            )

            correlation = np.fft.ifft(np.fft.fft(shifted_samples) * prn_code_fft_conj)

            coherent_sums[i] += correlation
            magnitude_sums[i] += np.abs(correlation)

    frequency_shift_index, prn_code_phase = np.unravel_index(
        np.argmax(magnitude_sums), magnitude_sums.shape
    )

    peak_correlation = magnitude_sums[frequency_shift_index, prn_code_phase]
    mean_correlation = np.mean(
        magnitude_sums[
            frequency_shift_index,
            magnitude_sums[frequency_shift_index] != peak_correlation,
        ]
    )

    return Acquisition(
        carrier_frequency_shift=frequency_shifts[frequency_shift_index],
        carrier_phase_shift=np.angle(
            coherent_sums[frequency_shift_index, prn_code_phase]
        ),
        prn_code_phase_shift=int(prn_code_phase),
        satellite_id=satellite_id,
        strength=peak_correlation / mean_correlation,
        timestamp=samples[-1].end_timestamp,
    )
