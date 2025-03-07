import logging

import numpy as np

from .config import PREAMBLES_REQUIRED_TO_DETERMINE_BIT_PHASE
from .constants import BITS_PER_SUBFRAME
from .subframe_decoder import SubframeDecoder
from .types import Bit, BitPhase, Pseudobit, SatelliteId
from .utils import invariant

# How many pseudobits we must collect before we may attempt to determine the
# boundaries between subframes and the overall bit phase.
#
# We'll likely start collecting them part way through a subframe. This means
# that even after we've collected ``PREAMBLES_REQUIRED_TO_DETERMINE_BIT_PHASE``
# subframes' worth of pseudobits, the number of preambles we find will likely be one
# fewer than that. Add one to the constant to avoid this issue.
_PSEUDOBITS_REQUIRED_TO_DETERMINE_BIT_PHASE = (
    PREAMBLES_REQUIRED_TO_DETERMINE_BIT_PHASE + 1
) * BITS_PER_SUBFRAME

# The fixed TLM word preamble and its inverse.
#
# These are used to determine the boundaries between subframes and the overall
# bit phase. They're defined as ``Pseudobit``s rather than ``Bit``s so they
# can be matched against the collected array of ``Pseudobit``s.
_TLM_PREAMBLE: list[Pseudobit] = [1, -1, -1, -1, 1, -1, 1, 1]
_INVERSE_TLM_PREAMBLE: list[Pseudobit] = [-1, 1, 1, 1, -1, 1, -1, -1]

logger = logging.getLogger(__name__)


class PseudobitIntegrator:
    """Integrates ``Pseudobits`` into subframes.

    Each subframe is 300 bits long and starts with a telemetry word which in
    turn starts with a preamble that's the same for every subframe. We can use
    this to find the boundaries between subframes and the overall bit phase.

    This class takes ``Pseudobit``s from a ``PseudosymbolIntegrator``,
    determines which groups of 300 bits should be considered a subframe, and
    forwards the results to a ``SubframeDecoder``.
    """

    def __init__(
        self, satellite_id: SatelliteId, subframe_decoder: SubframeDecoder
    ) -> None:
        # The overall bit phase.
        #
        # ``None`` means we haven't determined it yet.
        self._bit_phase: BitPhase | None = None

        self._pseudobits: list[Pseudobit] = []
        self._satellite_id = satellite_id
        self._subframe_decoder = subframe_decoder

    @property
    def bit_phase(self) -> BitPhase | None:
        return self._bit_phase

    def handle_pseudobit(self, pseudobit: Pseudobit) -> None:
        self._pseudobits.append(pseudobit)

        # Determine the bit phase.
        if (
            len(self._pseudobits) >= _PSEUDOBITS_REQUIRED_TO_DETERMINE_BIT_PHASE
            and self._bit_phase is None
        ):
            self._determine_bit_phase()

        # Group bits into subframes as long as we have enough data.
        while (
            len(self._pseudobits) >= BITS_PER_SUBFRAME and self._bit_phase is not None
        ):
            pseudobits = self._pseudobits[:BITS_PER_SUBFRAME]
            del self._pseudobits[:BITS_PER_SUBFRAME]

            bits = [self._resolve_bit(ub) for ub in pseudobits]
            self._subframe_decoder.handle_bits(bits)

    def _determine_bit_phase(self) -> None:
        invariant(self._bit_phase is None, "The bit phase has already been determined")

        for offset in range(BITS_PER_SUBFRAME):
            pseudobits = self._pseudobits[offset:]
            determined = False

            # If each subframe in ``pseudobits`` starts with the TLM preamble
            # (or its inverse) then we've found the boundaries between subframes
            # and can determine the overall bit phase.
            #
            # If ``offset`` is non-zero then there's a partial subframe at the
            # start of ``self._pseudobits`` which can be discarded.
            if self._all_subframes_start_with_preamble(_TLM_PREAMBLE, pseudobits):
                determined = True
                self._bit_phase = 1
            elif self._all_subframes_start_with_preamble(
                _INVERSE_TLM_PREAMBLE, pseudobits
            ):
                determined = True
                self._bit_phase = -1

            if determined:
                del self._pseudobits[:offset]
                logger.info(
                    f"[{self._satellite_id}] Determined bit phase: {self._bit_phase}"
                )
                return

        raise UnknownBitPhaseError()

    def _all_subframes_start_with_preamble(
        self, preamble: list[Pseudobit], pseudobits: list[Pseudobit]
    ) -> bool:
        """Determines if all subframes in ``pseudobits`` start with ``preamble``.

        Assumes the first subframe starts at index 0, the second at 300, etc.
        If the length of ``pseudobits`` isn't an integer multiple of
        ``BITS_PER_SUBFRAME`` the leftover bits at the end are ignored.
        """
        invariant(
            len(preamble) <= len(pseudobits),
            "The preamble must be equal or shorter in length than the pseudobits",
        )
        invariant(
            len(pseudobits) >= BITS_PER_SUBFRAME,
            "Not enough pseudobits for a subframe",
        )

        for i in range(0, len(pseudobits) - (BITS_PER_SUBFRAME - 1), BITS_PER_SUBFRAME):
            if not np.array_equal(preamble, pseudobits[i : i + len(preamble)]):
                return False

        return True

    def _resolve_bit(self, pseudobit: Pseudobit) -> Bit:
        invariant(
            self._bit_phase is not None,
            "A bit can't be resolved until the bit phase is determined",
        )

        if self._bit_phase == -1:
            return 1 if pseudobit == -1 else 0
        else:
            return 0 if pseudobit == -1 else 1


class UnknownBitPhaseError(Exception):
    """Indicates that we weren't able to determine a satellite's bit phase.

    This suggests we're not tracking the satellite correctly.
    """

    pass
