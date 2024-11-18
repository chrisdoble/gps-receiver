from collections import deque
from dataclasses import dataclass

import numpy as np

from .antenna import OneMsOfSamples
from .config import (
    ACQUISITION_INTERVAL_SECONDS,
    ACQUISITION_STRENGTH_THRESHOLD,
    ALL_SATELLITE_IDS,
    MS_OF_SAMPLES_REQUIRED_TO_PERFORM_ACQUISITION,
    SAMPLE_TIMESTAMPS,
    SAMPLES_PER_MILLISECOND,
    SAMPLES_PER_SECOND,
)
from .prn_codes import COMPLEX_UPSAMPLED_PRN_CODES_BY_SATELLITE_ID
from .units import SampleTimestampSeconds, SatelliteId


@dataclass
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


class Acquirer:
    """Detects GPS satellite signals and determines their parameters."""

    def __init__(self) -> None:
        self._acquisition_last_performed_at: SampleTimestampSeconds = 0
        self._samples = deque[OneMsOfSamples](
            maxlen=MS_OF_SAMPLES_REQUIRED_TO_PERFORM_ACQUISITION
        )

    def handle_1ms_of_samples(
        self, samples: OneMsOfSamples, tracked_satellite_ids: set[SatelliteId]
    ) -> list[Acquisition]:
        """Handle 1 ms of samples.

        This may simply store the samples for future use or it could result in
        attempting acquisition of satellites that aren't already being tracked
        (as determined by ``tracked_satellite_ids``) depending on how many ms of
        samples we've already collected and when we last attempted acquisition.
        """

        self._samples.append(samples)

        if len(self._samples) < MS_OF_SAMPLES_REQUIRED_TO_PERFORM_ACQUISITION:
            # We don't have enough samples to perform acquisition.
            return []

        if (
            self._acquisition_last_performed_at > 0
            and self._acquisition_last_performed_at + ACQUISITION_INTERVAL_SECONDS
            > samples.end_time
        ):
            # It hasn't been long enough since we last attempted acquisition.
            return []

        acquisitions = []
        untracked_satellite_ids = ALL_SATELLITE_IDS - tracked_satellite_ids

        for satellite_id in untracked_satellite_ids:
            acquisition = self._acquire_satellite(satellite_id)
            if acquisition is not None:
                acquisitions.append(acquisition)

        self._acquisition_last_performed_at = samples.end_time
        return acquisitions

    def _acquire_satellite(self, satellite_id: SatelliteId) -> Acquisition | None:
        """Attempts to acquire the signal of a particular GPS satellite.

        Returns an acquisition if it is strong enough, otherwise returns None.
        """
        # The following attempts to acquire the satellite's signal at a fixed
        # number of frequency shifts in a range around a central value. The
        # central value is updated to be the frequency shift of the strongest
        # candidate, the range is reduced, and the process is repeated until
        # we're searching a continuous range. This means we start by searching a
        # large range and gradually narrow down on the most promising regions.
        #
        # The initial central value is 0 and the initial frequency shift range
        # is ±7.168 kHz. This range was chosen to accommodate all reasonable
        # receiver and satellite motion, receiver oscillation variance, etc. On
        # each iteration the range is split into 29 equally-spaced values
        # (including endpoints) and is reduced by a factor of two. This means on
        # the first iteration the step size is 512 Hz, the second it's 256 Hz,
        # etc., until the tenth iteration where it's 1 Hz and we're searching a
        # continuous range. At that point we've found the strongest candidate.
        best_acquisition: Acquisition | None = None
        centre_frequency_shift: float = 0
        half_frequency_shift_range: float = 7_168

        while half_frequency_shift_range >= 14:
            new_acquisition = self._acquire_satellite_at_frequency_shifts(
                np.linspace(
                    centre_frequency_shift - half_frequency_shift_range,
                    centre_frequency_shift + half_frequency_shift_range,
                    29,
                ),
                satellite_id,
            )

            if (
                best_acquisition is None
                or new_acquisition.strength > best_acquisition.strength
            ):
                best_acquisition = new_acquisition

            centre_frequency_shift = best_acquisition.carrier_frequency_shift
            half_frequency_shift_range /= 2

        if (
            best_acquisition is not None
            and best_acquisition.strength >= ACQUISITION_STRENGTH_THRESHOLD
        ):
            return best_acquisition
        else:
            return None

    def _acquire_satellite_at_frequency_shifts(
        self, frequency_shifts: np.ndarray, satellite_id: SatelliteId
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
            for samples in self._samples:
                # Perform carrier wipeoff.
                shifted_samples = samples.samples * np.exp(
                    -2j * np.pi * f * (SAMPLE_TIMESTAMPS + samples.start_time)
                )

                correlation = np.fft.ifft(
                    np.fft.fft(shifted_samples) * prn_code_fft_conj
                )

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
        )
