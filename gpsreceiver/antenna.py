from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np

from . import config


class Antenna(ABC):
    """An antenna from which we can sample received signals as I/Q data.

    All antennas sample at a rate of ``gpsreceiver.config.SAMPLE_RATE``.
    """

    @abstractmethod
    def sample_1ms(self) -> np.ndarray:
        """Sample 1 ms of data from the antenna.

        The returned array has shape ``(config.SAMPLES_PER_MILLISECOND,)`` and
        contains ``complex`` values.
        """

        pass


class FileAntenna(Antenna):
    """An antenna backed by a file containing I/Q data.

    It's assumed that the file contains a list of 32-bit floating point numbers
    with each pair representing a single complex value (I/Q sample).
    """

    def __init__(self, path: Path) -> None:
        self.file_size_in_bytes = path.stat().st_size
        self.offset_in_bytes: int = 0
        self.path = path

    def sample_1ms(self) -> np.ndarray:
        count = config.SAMPLES_PER_MILLISECOND * 2
        dtype = np.dtype(np.float32)
        size_in_bytes = count * dtype.itemsize

        if self.offset_in_bytes + size_in_bytes >= self.file_size_in_bytes:
            raise EOFError()

        data = np.fromfile(
            self.path,
            count=count,
            dtype=dtype,
            offset=self.offset_in_bytes,
        )
        self.offset_in_bytes += size_in_bytes
        return data[0::2] + (1j * data[1::2])
