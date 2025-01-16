from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Annotated, Literal

import numpy as np
from pydantic import Field

from .constants import SAMPLES_PER_SECOND, SECONDS_PER_SAMPLE

# A bit.
#
# This is the result of ``BitIntegrator`` determining the overall bit phase and
# applying it to an ``UnresolvedBit``. There's no phase ambiguity here.
Bit = Literal[0, 1]

# A signal's bit phase.
#
# -1 means -1 maps to 1 and 1 maps to 0. 1 means the opposite.
BitPhase = Literal[-1, 1]

# A pseudosymbol emitted by a ``Tracker``.
#
# Can also be considered one twentieth of a navigation bit.
#
# Defined as -1 or 1 rather than 0 or 1 because the latter suggests we know how
# pseudosymbols map to bits. However, due to the phase ambiguity of BPSK, we
# don't know how they map until the overall phase of the signal is determined.
Pseudosymbol = Literal[-1, 1]


@dataclass(kw_only=True)
class Samples:
    """A set of samples taken at a rate of ``constants.SAMPLES_PER_SECOND``."""

    # The time just after the last sample was taken.
    end_timestamp: UtcTimestamp

    # The samples.
    #
    # Has shape ``(n,)`` where ``n`` is the number of samples that were taken
    # and contains ``np.complex64`` values.
    samples: np.ndarray

    # The time just before the first sample was taken.
    start_timestamp: UtcTimestamp

    def __add__(self, other: Samples) -> Samples:
        """Concatenates two sets of samples.

        When concatenating two sets of samples ``x + y``, it is assumed that
        ``y`` immediately follows ``x`` in time. This means it makes sense to:

        - use the start timestamp of ``x`` as the start timestamp of the result,
        - use the end timestamp of ``y`` as the end timestamp of the result, and
        - use the concatentation of ``x``'s samples followed by ``y``'s samples
          as the samples of the result.
        """

        return Samples(
            end_timestamp=other.end_timestamp,
            samples=np.concatenate((self.samples, other.samples)),
            start_timestamp=self.start_timestamp,
        )

    def __getitem__(self, key: slice) -> Samples:
        """Returns a subset of the samples.

        For example, if ``x`` contains 2046 samples then ``x[0 : 1023]``
        contains the first 1023 samples with appropriate timestamps.

        Empty slices and negative indices aren't supported.
        """

        # Check that the slice bounds are of the correct type.
        if not (
            (isinstance(key.start, int) or key.start is None)
            and (isinstance(key.stop, int) or key.stop is None)
            and key.step is None
        ):
            raise TypeError("Invalid slice")

        start = 0 if key.start is None else key.start
        stop = len(self.samples) if key.stop is None else key.stop

        # Check that the slice bounds are valid indices.
        if not (
            start >= 0
            and start < len(self.samples)
            and stop >= 0
            and stop <= len(self.samples)
            and stop > start
        ):
            raise IndexError("Invalid slice")

        return Samples(
            end_timestamp=self.start_timestamp
            + timedelta(seconds=stop * SECONDS_PER_SAMPLE),
            samples=self.samples[start:stop],
            start_timestamp=self.start_timestamp
            + timedelta(seconds=start * SECONDS_PER_SAMPLE),
        )


# 1 ms of samples.
#
# This type primarily exists for documentation purposes.
OneMsOfSamples = Samples


# The ID of a GPS satellite based on its PRN number. This can be an integer
# between 1 and 32 inclusive, but PRN number 1 is not currently in use[1].
#
# 1: https://en.wikipedia.org/wiki/List_of_GPS_satellites#PRN_status_by_satellite_block
SatelliteId = Annotated[int, Field(ge=1, le=32)]


class Side(Enum):
    """A side of a chunk of samples."""

    # The left side (earlier in time).
    LEFT = 0

    # The right side (later in time).
    RIGHT = 1


# A phase ambiguous bit emitted by a ``PseudosymbolIntegrator``.
#
# ``PseudosymbolIntegrator`` identifies groups of pseudosymbols that correspond
# to the same underlying navigation bit, determines the predominant phase within
# that group, and emits the result. We can't call these navigation bits yet
# because we haven't applied the bit phase. This is one of those values.
UnresolvedBit = Literal[-1, 1]

# A datetime in the UTC time zone.
#
# The time zone isn't enforced by this type, but the name is a helpful reminder.
UtcTimestamp = datetime
