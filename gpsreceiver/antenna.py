from abc import ABC, abstractmethod
from datetime import timedelta
from pathlib import Path

import numpy as np

from .config import SAMPLES_PER_MILLISECOND
from .constants import SAMPLES_PER_SECOND
from .types import OneMsOfSamples, UtcTimestamp


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

    def __init__(self, path: Path, start_timestamp: UtcTimestamp) -> None:
        self._dtype = np.dtype(np.float32)
        self._file_size_in_samples = path.stat().st_size // self._dtype.itemsize // 2
        self._offset_in_samples: int = 0
        self._path = path
        self._start_timestamp = start_timestamp

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

        old_offset_in_samples = self._offset_in_samples
        self._offset_in_samples += SAMPLES_PER_MILLISECOND

        return OneMsOfSamples(
            end_timestamp=self._start_timestamp
            + timedelta(seconds=self._offset_in_samples / SAMPLES_PER_SECOND),
            samples=data[0::2] + (1j * data[1::2]),
            start_timestamp=self._start_timestamp
            + timedelta(seconds=old_offset_in_samples / SAMPLES_PER_SECOND),
        )
