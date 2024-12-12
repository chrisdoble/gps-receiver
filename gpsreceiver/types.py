from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Literal

import numpy as np

# A bit.
#
# This is the result of ``BitIntegrator`` determining the overall bit phase and
# applying it to an ``UnresolvedBit``. There's no phase ambiguity here.
Bit = Literal[0, 1]

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
    """A number of samples taken at a rate of ``constants.SAMPLES_PER_SECOND``."""

    # The time just after the last sample was taken.
    end_timestamp: UtcTimestamp

    # The samples.
    #
    # Has shape ``(n,)`` where ``n`` is the number of samples that were taken
    # and contains ``np.complex64`` values.
    samples: np.ndarray

    # The time just before the first sample was taken.
    start_timestamp: UtcTimestamp


# 1 ms of samples.
#
# This type primarily exists for documentation purposes.
OneMsOfSamples = Samples


# The ID of a GPS satellite based on its PRN number. This can be an integer
# between 1 and 32 inclusive, but PRN number 1 is not currently in use[1].
#
# 1: https://en.wikipedia.org/wiki/List_of_GPS_satellites#PRN_status_by_satellite_block
SatelliteId = int


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
