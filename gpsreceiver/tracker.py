import math
from collections import deque
from datetime import timedelta

import numpy as np

from .acquirer import Acquisition
from .antenna import OneMsOfSamples
from .config import (
    CARRIER_FREQUENCY_SHIFT_TRACKING_LOOP_GAIN,
    CARRIER_PHASE_SHIFT_TRACKING_LOOP_GAIN,
    PRN_CODE_PHASE_SHIFT_TRACKING_LOOP_GAIN,
)
from .constants import SAMPLE_TIMES, TRACKING_HISTORY_SIZE
from .prn_codes import COMPLEX_UPSAMPLED_PRN_CODES_BY_SATELLITE_ID
from .pseudosymbol_integrator import PseudosymbolIntegrator
from .utils import invariant
from .world import World


class Tracker:
    """Tracks a satellite's signal and decodes pseudosymbols."""

    def __init__(
        self,
        acquisition: Acquisition,
        pseudosymbol_integrator: PseudosymbolIntegrator,
        world: World,
    ) -> None:
        # The most recent estimates of the carrier's frequency shift in Hz.
        self._carrier_frequency_shifts = deque[float](
            [acquisition.carrier_frequency_shift], maxlen=TRACKING_HISTORY_SIZE
        )

        # The most recent estimates of the carrier's phase shift in radians.
        self._carrier_phase_shifts = deque[float](
            [acquisition.carrier_phase_shift], maxlen=TRACKING_HISTORY_SIZE
        )

        # The most recent correlations of 1 ms of received signal and the prompt
        # local replica. These can be used to plot a constellation diagram.
        self._correlations = deque[complex]([], maxlen=TRACKING_HISTORY_SIZE)

        # The satellite's complex, upsampled PRN code.
        self._prn_code = COMPLEX_UPSAMPLED_PRN_CODES_BY_SATELLITE_ID[
            acquisition.satellite_id
        ]

        self._prn_code_length = len(self._prn_code)

        # The most recent estimates of the PRN code's phase shift in half-chips.
        #
        # The values are floats because the delay-locked-loop that tracks the
        # PRN code phase shift gradually changes it by adding floating-point
        # values. When we actually need to use them we cast them to integers.
        self._prn_code_phase_shifts = deque[float](
            [acquisition.prn_code_phase_shift], maxlen=TRACKING_HISTORY_SIZE
        )

        self._pseudosymbol_integrator = pseudosymbol_integrator
        self._satellite_id = acquisition.satellite_id
        self._world = world

    def handle_1ms_of_samples(self, samples: OneMsOfSamples) -> None:
        """Uses 1 ms of samples to determine the transmitted pseudosymbol and
        update tracking parameters."""

        # Perform carrier wipeoff.
        shifted_samples = samples.samples * np.exp(
            -1j
            * (
                2 * np.pi * self._carrier_frequency_shift * SAMPLE_TIMES
                + self._carrier_phase_shift
            )
        )

        # Update the PRN code phase shift.
        prn_count_adjustment = self._track_prn_code_phase_shift(shifted_samples)

        # Report the number of trailing edges of PRN codes we've observed in
        # this 1 ms period (if any). Usually we observe one, but it's also
        # possible to observe 0 or 2 if the PRN code phase shift has wrapped.
        prn_count = 1 + prn_count_adjustment
        if prn_count > 0:
            self._world.handle_prn_codes(
                prn_count,
                self._satellite_id,
                # Calculate the time of the trailing edge of the last PRN code.
                samples.start_timestamp
                + timedelta(
                    seconds=self._prn_code_phase_shift / self._prn_code_length / 1000
                ),
            )

        # Calculate the correlation of the shifted samples and the prompt local
        # replica. If our estimates are good, multiplying the shifted samples by
        # the prompt local replica removes the PRN code, leaving only the
        # navigation bit. The correlation is thus the navigation by times the
        # number of samples per millisecond - hopefully a (mostly) real number.
        #
        # No need to take the conjucate of the replica - it only contains ±1.
        prn_code = np.roll(self._prn_code, int(self._prn_code_phase_shift))
        correlation = np.sum(shifted_samples * prn_code)
        self._correlations.append(correlation)

        # Decode and handle the pseudosymbol.
        self._pseudosymbol_integrator.handle_pseudosymbol(
            -1 if correlation.real < 0 else 1
        )

        # Update the carrier wave frequency/phase shift.
        self._track_carrier(correlation)

    @property
    def _carrier_frequency_shift(self) -> float:
        """Returns the most recent estimate of the carrier wave's frequency
        shift in Hz."""

        invariant(len(self._carrier_frequency_shifts) > 0)
        return self._carrier_frequency_shifts[-1]

    @property
    def _carrier_phase_shift(self) -> float:
        """Returns the most recent estimate of the carrier wave's phase shift in
        radians."""

        invariant(len(self._carrier_phase_shifts) > 0)
        return self._carrier_phase_shifts[-1]

    def _track_prn_code_phase_shift(self, shifted_samples: np.ndarray) -> int:
        """Tracks the C/A PRN code's phase shift using a delay-locked loop.

        Returns an integer in the range [-1, 1] indicating how this satellite's
        observed PRN count should be adjusted. This is required because wrapping
        of the PRN code phase shift from 0 to 2046 implies we've seen one extra
        PRN code and wrapping from 2046 to 0 implies we've seen one fewer.
        """

        # Generate replicas that are early and late by a half-chip.
        early = np.roll(self._prn_code, int(self._prn_code_phase_shift - 1))
        late = np.roll(self._prn_code, int(self._prn_code_phase_shift + 1))

        # Calculate the correlation of the shifted samples and the replicas.
        #
        # No need to take the conjugate of the replicas - they only contain ±1.
        early_correlation = np.sum(shifted_samples * early)
        late_correlation = np.sum(shifted_samples * late)

        # Calculate the discriminator.
        #
        # This the non-coherent early minus late power discriminator. It is
        # defined here[1], is used by Gypsum[2], and was suggested by Claude.
        #
        # 1: https://gssc.esa.int/navipedia/index.php/Delay_Lock_Loop_(DLL)#Discriminators
        # 2: https://github.com/codyd51/gypsum/blob/b9a5b4ec98557cf107f589dbffa0ad522851c14c/gypsum/tracker.py#L297
        discriminator = (
            (early_correlation.real**2 + early_correlation.imag**2)
            - (late_correlation.real**2 + late_correlation.imag**2)
        ) / 2

        # Calculate the number of additional (or fewer) half chips that will be
        # present in 1 ms of samples due to Doppler shift of the carrier wave.
        #
        # If a satellite's carrier wave has been Doppler shifted, so too will
        # the PRN code within. It will stretch or shrink in time and it will no
        # longer be the case that 1 ms of samples contains exactly one cycle.
        # We need to account for this when updating the phase shift, otherwise
        # the differences will accumulate over time and we'll lose lock.
        l1_frequency = 1575.42e6
        half_chips_due_to_doppler_effect = (
            len(self._prn_code) * self._carrier_frequency_shift / l1_frequency
        )

        # Update the PRN code phase shift.
        prn_code_phase_shift = (
            self._prn_code_phase_shift
            - discriminator * PRN_CODE_PHASE_SHIFT_TRACKING_LOOP_GAIN
            - half_chips_due_to_doppler_effect
        )

        # Ensure it's in the range [0, len(self._prn_code)). If it wraps, record
        # the adjustment we must make to this satellite's observed PRN count.
        prn_count_adjustment = 0

        if prn_code_phase_shift < 0:
            prn_code_phase_shift += self._prn_code_length
            prn_count_adjustment = 1
        elif prn_code_phase_shift >= self._prn_code_length:
            prn_code_phase_shift -= self._prn_code_length
            prn_count_adjustment = -1

        self._prn_code_phase_shifts.append(prn_code_phase_shift)
        return prn_count_adjustment

    @property
    def _prn_code_phase_shift(self) -> float:
        """Returns the most recent estimate of the C/A PRN code's phase shift in
        half-chips."""

        invariant(len(self._prn_code_phase_shifts) > 0)
        return self._prn_code_phase_shifts[-1]

    def _track_carrier(self, correlation: complex) -> None:
        """Tracks the carrier wave's frequency and phase shifts using a Costas
        loop.

        ``correlation`` is the correlation between the (post wipeoff) received
        signal and the prompt local replica of the PRN code.
        """
        # The received signal can be expressed as
        # n(t) * prn_code(t) * exp(2 π ((f + Δf) t + θ)) where n(t) = ±1 is the
        # navigation bit at time t, prn_code(t) = ±1 is the PRN code chip at
        # time t, exp(...) is the exponential function, f is the L1 frequency
        # 1.56542 GHz, Δf is the signal's frequency shift due to the Doppler
        # effect, and θ is the phase of the carrier wave.
        #
        # If we undersample the antenna such that the L1 frequency is aliased at
        # 0 Hz, f disappears from this expression leaving
        # n(t) * prn_code(t) * exp(2 π (Δf t + θ)).
        #
        # If we're tracking the carrier wave well (i.e. our estimates of Δf and
        # θ are good), carrier wipeoff removes the exponential term leaving
        # n(t) * prn_code(t).
        #
        # If we're tracking the PRN code phase shift well (i.e. our local
        # replica is equal to prn_code(t)) then multiplying the (post wipeoff)
        # signal by the local replica leaves
        #
        #     n(t) * prn_code(t) * prn_code(t)
        #     = n(t) * prn_code(t) ** 2
        #     = n(t) * (±1) ** 2
        #     = n(t).
        #
        # In other words, if we're tracking the signal well, the correlation of
        # the (post wipeoff) signal and the local replica of the PRN code will
        # be the value of the navigation bit during that period multiplied by
        # the sampling rate - a real value. If we find that the correlation
        # isn't (at least mostly) real, our estimates of Δf, θ, and/or the PRN
        # code phase shift are wrong. For this reason we use the complex
        # argument of the correlation as the error signal in this loop.

        # Normalise the correlation so the loop is independent of signal
        # amplitude. A small epsilon value is added to avoid numerical
        # instability when the correlation itself has a small magnitude.
        correlation /= abs(correlation) + 1e-8

        # Calculate the error signal.
        #
        # We want each correlation to be a real value, i.e. have no imaginary
        # component. Some correlations correspond to binary 0s and will lay on
        # one side of the Q axis while others correspond to binary 1s and will
        # lay on the other side. This 180° phase shift between 0s and 1s means
        # we can't simply use the complex argument of the correlation as the
        # error signal as it would try to move both to the positive I axis.
        # Instead we use the complex argument as calculated by ``math.atan``
        # which is restricted to the range [-π/2, π/2]. This means the error
        # signal will tend to move correlations towards their closest I axis.
        #
        # Later on we determine the overall phase, i.e. are correlations on the
        # negative I axis 0s and those on the positive I axis 1s, or vice versa?
        error = (
            0
            if correlation.real == 0
            else math.atan(correlation.imag / correlation.real)
        )

        # The interval between successive Tracker updates in seconds.
        tracker_update_interval = 0.001

        # Update the carrier wave's frequency shift.
        self._carrier_frequency_shifts.append(
            self._carrier_frequency_shift
            + CARRIER_FREQUENCY_SHIFT_TRACKING_LOOP_GAIN
            * error
            * tracker_update_interval
        )

        # Update the carrier wave's phase shift.
        #
        # It's important that this include the current estimate of the carrier
        # frequency shift to account for the change in phase it will cause in
        # between Tracker updates. This is why we update the estimate of the
        # carrier frequency shift first - to ensure we're using the latest data.
        carrier_phase_shift = (
            self._carrier_phase_shift
            + (
                CARRIER_PHASE_SHIFT_TRACKING_LOOP_GAIN * error
                + 2 * np.pi * self._carrier_frequency_shift
            )
            * tracker_update_interval
        )
        carrier_phase_shift %= 2 * np.pi
        self._carrier_phase_shifts.append(carrier_phase_shift)
