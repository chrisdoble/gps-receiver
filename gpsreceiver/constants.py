"""This module contains commonly used values whose definitions shouldn't change,
either because they're defined in the GPS spec (e.g. ``BITS_PER_SUBFRAME``) or
because they're derived from other values (e.g. ``SAMPLES_PER_SECOND``)."""

import numpy as np

from .config import SAMPLES_PER_MILLISECOND, TRACKING_HISTORY_SIZE_SECONDS

# Sampling

SAMPLES_PER_SECOND = SAMPLES_PER_MILLISECOND * 1000

# The timestamp of each sample within a 1 ms sampling period.
SAMPLE_TIMESTAMPS = np.arange(SAMPLES_PER_MILLISECOND) / SAMPLES_PER_SECOND

# Tracking

# The number of values to be stored in each tracking history buffer.
#
# This assumes we recalculate tracking parameters once per millisecond.
TRACKING_HISTORY_SIZE = int(TRACKING_HISTORY_SIZE_SECONDS * 1000)

# Navigation data demodulation

# The number of bits contained within a subframe of the navigation message.
# Defined in section 20.3.2 of IS-GPS-200.
BITS_PER_SUBFRAME = 300
