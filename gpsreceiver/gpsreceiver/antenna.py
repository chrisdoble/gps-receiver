import signal
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
from rtlsdr import RtlSdr

from .config import SAMPLES_PER_MILLISECOND
from .constants import L1_FREQUENCY, SAMPLES_PER_SECOND, SECONDS_PER_SAMPLE
from .receiver import Receiver
from .types import OneMsOfSamples, Samples, UtcTimestamp


class Antenna(ABC):
    """An antenna that samples signals as I/Q data.

    All antennas sample at a rate of ``gpsreceiver.config.SAMPLE_RATE``.
    """

    def __init__(self, receiver: Receiver) -> None:
        self._receiver = receiver

    @abstractmethod
    def start(self) -> None:
        """Start sampling and passing the samples to the ``Receiver``.

        This method blocks.
        """

        pass


class FileAntenna(Antenna):
    """An antenna backed by a file containing I/Q data.

    It's assumed that the file contains a list of 32-bit floating point numbers
    with each pair representing a single complex value (an I/Q sample).
    """

    def __init__(
        self, path: Path, receiver: Receiver, start_timestamp: UtcTimestamp
    ) -> None:
        super().__init__(receiver)

        self._dtype = np.dtype(np.float32)
        self._file_size_in_samples = path.stat().st_size // self._dtype.itemsize // 2
        self._offset_in_samples: int = 0
        self._path = path
        self._start_timestamp = start_timestamp

    def start(self) -> None:
        while True:
            self._receiver.handle_1ms_of_samples(self._sample_1ms())

    def _sample_1ms(self) -> OneMsOfSamples:
        if (
            self._offset_in_samples + SAMPLES_PER_MILLISECOND
            >= self._file_size_in_samples
        ):
            raise EOFError("No more samples")

        data = np.fromfile(
            self._path,
            count=SAMPLES_PER_MILLISECOND * 2,
            dtype=self._dtype,
            offset=self._offset_in_samples * 2 * self._dtype.itemsize,
        )

        old_offset_in_samples = self._offset_in_samples
        self._offset_in_samples += SAMPLES_PER_MILLISECOND

        return OneMsOfSamples(
            end_timestamp=self._start_timestamp
            + timedelta(seconds=self._offset_in_samples / SAMPLES_PER_SECOND),
            samples=data[0::2] + (1j * data[1::2]),
            start_timestamp=self._start_timestamp
            + timedelta(seconds=old_offset_in_samples / SAMPLES_PER_SECOND),
        )


class RtlSdrAntenna(Antenna):
    """An antenna backed by an RTL-SDR receiver.

    It's assumed that a single RTL-SDR is connected to the computer.
    """

    def __init__(self, receiver: Receiver) -> None:
        super().__init__(receiver)

        # pyrtlsdr requires that you receive a multiple of 512 samples at a
        # time. The number of samples we take per millisecond may not be a
        # multiple of 512, in which case there will be some "leftover" samples.
        #
        # This attribute is used to store the leftover samples which are
        # prepended to the next chunk of samples and forwarded to the receiver.
        self._samples: Samples | None = None

    def start(self) -> None:
        rtl_sdr = RtlSdr()
        rtl_sdr.set_bandwidth(SAMPLES_PER_SECOND)
        rtl_sdr.set_bias_tee(True)
        rtl_sdr.set_center_freq(L1_FREQUENCY)
        rtl_sdr.set_gain(20)
        rtl_sdr.set_sample_rate(SAMPLES_PER_SECOND)

        signal.signal(signal.SIGINT, lambda signal, frame: rtl_sdr.cancel_read_async())

        # The sample count must be a multiple of 512.
        rtl_sdr.read_samples_async(self._on_samples, 2048)

    def _on_samples(self, samples: np.ndarray, _: RtlSdr) -> None:
        # Concatenate the leftover samples (if any) and the new samples.
        now = datetime.now(timezone.utc)
        samples_ = Samples(
            end_timestamp=now,
            samples=samples,
            start_timestamp=now - timedelta(seconds=len(samples) * SECONDS_PER_SAMPLE),
        )
        self._samples = samples_ if self._samples is None else self._samples + samples_

        # While we have enough samples, forward them to the receiver.
        while len(self._samples.samples) > SAMPLES_PER_MILLISECOND:
            self._receiver.handle_1ms_of_samples(
                self._samples[0:SAMPLES_PER_MILLISECOND]
            )
            self._samples = self._samples[SAMPLES_PER_MILLISECOND:]
