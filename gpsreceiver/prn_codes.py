"""This module generates the GPS satellites' C/A PRN codes.

The PRN codes are generated by XORing the output of two linear-feedback shift
registers (LFSRs). Some documents say the second LFSR is delayed by a certain
number of chips while others say the output of the second LFSR is the XOR of
different stages per satellite. It turns out these approaches are equivalent.
Here we use the latter approach because it requires generating fewer outputs.
"""

import json
import math
from typing import Iterator

import numpy as np

from .config import SAMPLES_PER_MILLISECOND
from .types import SatelliteId
from .utils import invariant


def _lfsr(outputs: list[int], taps: list[int]) -> Iterator[int]:
    """Generates the output of a 10-stage linear-feedback shift register.

    ``outputs`` contains the (one-based) indices of the bits that are used to
    calculate the LFSR's output on each iteration, e.g. if ``outputs = [1, 2]``
    the output would be ``bits[0] ^ bits[1]``.

    Similarly, ``taps`` contains the (one-based) indices of the bits that are
    used to calculate the LFSR's leftmost bit on each iteration.

    The LFSR is seeded with ones.

    One-based indices are used to better match the GPS spec.
    """
    bits = [1 for _ in range(10)]

    while True:
        output = sum([bits[i - 1] for i in outputs]) % 2
        yield output

        feedback = sum(bits[i - 1] for i in taps) % 2

        for i in range(9, 0, -1):
            bits[i] = bits[i - 1]

        bits[0] = feedback


# The (one-based) output indices used to generate each satellite's C/A PRN code,
# indexed by satellite ID.
#
# Taken from Table 3-Ia in the GPS spec[1].
#
# 1: https://www.gps.gov/technical/icwg/IS-GPS-200M.pdf
_prn_code_outputs: dict[SatelliteId, list[int]] = {
    1: [2, 6],
    2: [3, 7],
    3: [4, 8],
    4: [5, 9],
    5: [1, 9],
    6: [2, 10],
    7: [1, 8],
    8: [2, 9],
    9: [3, 10],
    10: [2, 3],
    11: [3, 4],
    12: [5, 6],
    13: [6, 7],
    14: [7, 8],
    15: [8, 9],
    16: [9, 10],
    17: [1, 4],
    18: [2, 5],
    19: [3, 6],
    20: [4, 7],
    21: [5, 8],
    22: [6, 9],
    23: [1, 3],
    24: [4, 6],
    25: [5, 7],
    26: [6, 8],
    27: [7, 9],
    28: [8, 10],
    29: [1, 6],
    30: [2, 7],
    31: [3, 8],
    32: [4, 9],
}

# The C/A PRN codes of all GPS satellites, indexed by satellite ID.
PRN_CODES_BY_SATELLITE_ID: dict[SatelliteId, np.ndarray] = {}

for satellite_id, outputs in _prn_code_outputs.items():
    g1 = _lfsr([10], [3, 10])
    g2 = _lfsr(outputs, [2, 3, 6, 8, 9, 10])
    prn_code = np.empty(1023, np.float32)
    for i in range(1023):
        prn_code[i] = next(g1) ^ next(g2)
    PRN_CODES_BY_SATELLITE_ID[satellite_id] = prn_code

# The same C/A PRN codes as above, but upsampled so the number of chips in each
# is equal to the number of samples present in 1 ms of a received signal.
#
# This requires that SAMPLES_PER_MILLISECOND is an integer multiple of the
# length of a C/A PRN code (1023). Raises an exception if that's not the case.
invariant(
    SAMPLES_PER_MILLISECOND % len(PRN_CODES_BY_SATELLITE_ID[1]) == 0,
    "SAMPLES_PER_MILLISECOND isn't an integer multiple of the number of chips in a C/A PRN code (1023)",
)
_repeat_count = SAMPLES_PER_MILLISECOND // len(PRN_CODES_BY_SATELLITE_ID[1])
UPSAMPLED_PRN_CODES_BY_SATELLITE_ID = {
    satellite_id: np.repeat(prn_code, int(_repeat_count))
    for satellite_id, prn_code in PRN_CODES_BY_SATELLITE_ID.items()
}

# The same upsampled C/A PRN codes as above, but with 0 mapped to 1 and 1 to -1.
#
# As the data transmitted by a GPS satellite is modulated onto the carrier wave
# via BPSK, 0s and 1s result in signals that are 180 degrees out of phase. Thus,
# when we attempt to correlate a received signal with a local replica of a C/A
# PRN code we want the code chips to also be 180 degrees out of phase. Whether
# 0 is mapped to 1 and 1 to -1 or vice versa is arbitrary, but this mapping has
# the benefit that the XOR operation becomes equivalent to multiplication.
#
# This is also called polar non-return-to-zero encoding.
COMPLEX_UPSAMPLED_PRN_CODES_BY_SATELLITE_ID = {
    satellite_id: np.array([-1 if b == 1 else 1 for b in prn_code])
    for satellite_id, prn_code in UPSAMPLED_PRN_CODES_BY_SATELLITE_ID.items()
}
