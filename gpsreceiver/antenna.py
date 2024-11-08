from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .config import SAMPLES_PER_MILLISECOND, SAMPLES_PER_SECOND
from .units import SampleTimestampSeconds


@dataclass
class OneMsOfSamples:
    # The time just after the last sample was taken.
    end_time: SampleTimestampSeconds

    # 1 ms of I/Q samples. Has shape (config.SAMPLES_PER_MILLISECOND,) and
    # contains complex values.
    samples: np.ndarray

    # The time just before the first sample was taken.
    start_time: SampleTimestampSeconds


class Antenna(ABC):
    """An antenna from which we can sample received signals as I/Q data.

    All antennas sample at a rate of ``gpsreceiver.config.SAMPLE_RATE``.
    """

    @abstractmethod
    def sample_1ms(self) -> OneMsOfSamples:
        """Sample 1 ms of data from the antenna."""

        pass


class FileAntenna(Antenna):
    """An antenna backed by a file containing I/Q data.

    It's assumed that the file contains a list of 32-bit floating point numbers
    with each pair representing a single complex value (an I/Q sample).
    """

    def __init__(self, path: Path) -> None:
        self._dtype = np.dtype(np.float32)
        self._file_size_in_samples = path.stat().st_size // self._dtype.itemsize // 2
        self._offset_in_samples: int = 0
        self._path = path

    def sample_1ms(self) -> OneMsOfSamples:
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

        start_time = self._offset_in_samples / SAMPLES_PER_SECOND
        self._offset_in_samples += SAMPLES_PER_MILLISECOND

        return OneMsOfSamples(
            end_time=self._offset_in_samples / SAMPLES_PER_SECOND,
            samples=data[0::2] + (1j * data[1::2]),
            start_time=start_time,
        )
