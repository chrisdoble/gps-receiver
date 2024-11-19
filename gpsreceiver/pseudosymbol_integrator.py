from collections import Counter

import numpy as np

from .config import BITS_REQUIRED_TO_DETECT_BOUNDARIES
from .types import Pseudosymbol, UnresolvedBit

# How many pseudosymbols we must collect before we may attempt to determine
# the boundaries between navigation bits. There are 20 pseudosymbols per bit.
PSEUDOSYMBOLS_PER_BIT = 20
PSEUDOSYMBOLS_REQUIRED_TO_DETECT_BOUNDARIES = (
    BITS_REQUIRED_TO_DETECT_BOUNDARIES * PSEUDOSYMBOLS_PER_BIT
)

# How many pseudosymbols of each phase we must collect.
#
# If we're unlucky all of the pseudosymbols will be equal and it won't be
# possible to find the best offset. To avoid this we collect a minimum number of
# pseudosymbols of each phase (-1 and +1) before attempting to calculate the
# offset. This constant determines how many of each phase must be collected.
PSEUDOSYMBOLS_REQUIRED_PER_PHASE = PSEUDOSYMBOLS_REQUIRED_TO_DETECT_BOUNDARIES / 2


class PseudosymbolIntegrator:
    """Integrates pseudosymbols into bits.

    When a ``Tracker`` computes the correlation between a received signal and
    the prompt local replica, the sign of the real part of the result tells us
    the phase of the navigation bit at that time. This is called a pseudosymbol.

    Pseudosymbols are computed 1000 times per second and the navigation message
    is transmitted at 50 bps, so there are 20 pseudosymbols per navigation bit.
    In theory all 20 should have the same phase. In practice noise, samples
    taken during bit transitions, and weak signals cause some to be incorrect.

    This class takes pseudosymbols from a ``Tracker``, determines which groups
    of 20 pseudosymbols should be considered a single navigation bit, and
    forwards the results to a ``BitIntegrator``.
    """

    def __init__(self) -> None:
        # Whether we've found the boundary between navigation bits.
        self._is_synchronised = False

        self._pseudosymbols: list[Pseudosymbol] = []

    def handle_pseudosymbol(self, pseudosymbol: Pseudosymbol) -> None:
        self._pseudosymbols.append(pseudosymbol)

        # Synchronise if necessary…
        if not self._is_synchronised:
            # …but only if we have enough data.
            counter = Counter(self._pseudosymbols)
            if (
                counter[-1] >= PSEUDOSYMBOLS_REQUIRED_PER_PHASE
                and counter[1] >= PSEUDOSYMBOLS_REQUIRED_PER_PHASE
            ):
                self._synchronise()

        # Group pseudosymbols into bits as long as we have enough data.
        while (
            len(self._pseudosymbols) >= PSEUDOSYMBOLS_PER_BIT and self._is_synchronised
        ):
            # Extract the pseudosymbols comprising the next bit.
            pseudosymbols = self._pseudosymbols[:PSEUDOSYMBOLS_PER_BIT]
            del self._pseudosymbols[:PSEUDOSYMBOLS_PER_BIT]

            # Determine the (phase ambiguous) bit.
            counter = Counter(pseudosymbols)
            unresolved_bit: UnresolvedBit = counter.most_common(1)[0][0]
            print(unresolved_bit)

    def _synchronise(self) -> None:
        assert not self._is_synchronised, "Already synchronised"

        # Calculate a score for each possible offset.
        #
        # If an offset is good most of the pseudosymbols within each chunk will
        # be the same and the magnitude of their sum will be large. If an offset
        # is bad the pseudosymbols within each chunk will be mixed, they will
        # cancel each other, and the magnitude of their sum will be smaller.
        #
        # An offset's score is the mean of its chunks' sums.
        offset_scores: list[float] = []
        for offset in range(PSEUDOSYMBOLS_PER_BIT):
            chunks = _chunks(self._pseudosymbols[offset:], PSEUDOSYMBOLS_PER_BIT)
            offset_scores.append(np.mean(np.abs(np.sum(chunks, axis=1))))

        # Find the offset with the best score. If it is non-zero then there are
        # some pseudosymbols at the start of ``self._pseudosymbols`` that we
        # won't be able to group into a bit so they must be discarded.
        best_offset = np.argmax(offset_scores)
        self._pseudosymbols = self._pseudosymbols[best_offset:]

        self._is_synchronised = True


def _chunks[T](elements: list[T], chunk_size: int) -> list[list[T]]:
    """Splits ``elements`` into sub-lists of length ``chunk_size``.

    If the length of ``elements`` isn't an integer multiple of ``chunk_size``
    the leftover elements at the end of the array aren't included in the output.
    """

    return [
        elements[i : i + chunk_size]
        for i in range(0, len(elements) - (chunk_size - 1), chunk_size)
    ]
