import logging
from typing import Literal

import numpy as np

from .config import PREAMBLES_REQUIRED_TO_DETERMINE_BIT_PHASE
from .types import Bit, SatelliteId, UnresolvedBit

_BITS_PER_SUBFRAME = 300

# How many bits we must collect before we may attempt to determine the
# boundaries between subframes and the overall bit phase.
#
# We'll likely start collecting bits part way through a subframe. This means
# that even after we've collected ``PREAMBLES_REQUIRED_TO_DETERMINE_BIT_PHASE``
# subframes' worth of bits, the number of preambles we find will likely be one
# fewer than that. Add one to the constant to avoid this issue.
_BITS_REQUIRED_TO_DETERMINE_BIT_PHASE = (
    PREAMBLES_REQUIRED_TO_DETERMINE_BIT_PHASE + 1
) * _BITS_PER_SUBFRAME

# The fixed TLM word preamble and its inverse.
#
# These are used to determine the boundaries between subframes and the overall
# bit phase. They're defined as ``UnresolvedBit``s rather than ``Bit``s so they
# can be matched against the collected array of ``UnresolvedBit``s.
_TLM_PREAMBLE: list[UnresolvedBit] = [1, -1, -1, -1, 1, -1, 1, 1]
_INVERSE_TLM_PREAMBLE: list[UnresolvedBit] = [-1, 1, 1, 1, -1, 1, -1, -1]

logger = logging.getLogger(__name__)


class BitIntegrator:
    """Integrates bits into subframes.

    Each subframe is 300 bits long and starts with a telemetry (TLM) word which
    in turn starts with a preamble that's the same for every subframe. We can
    use this preamble to find the boundaries between subframes and the overall
    bit phase. The bits of each subframe are then forwarded in the pipeline.
    """

    def __init__(self, satellite_id: SatelliteId) -> None:
        # The overall bit phase.
        #
        # ``None`` means we haven't determined the overall bit phase yet. ``-1``
        # means ``-1`` maps to ``1`` and ``1`` to ``0``. ``1`` is the opposite.
        self._bit_phase: Literal[None, -1, 1] = None

        self._satellite_id = satellite_id
        self._unresolved_bits: list[UnresolvedBit] = []

    def handle_unresolved_bit(self, unresolved_bit: UnresolvedBit) -> None:
        self._unresolved_bits.append(unresolved_bit)

        # Determine the bit phase.
        if (
            len(self._unresolved_bits) >= _BITS_REQUIRED_TO_DETERMINE_BIT_PHASE
            and self._bit_phase is None
        ):
            self._determine_bit_phase()

        # Group bits into subframes as long as we have enough data.
        while (
            len(self._unresolved_bits) >= _BITS_PER_SUBFRAME
            and self._bit_phase is not None
        ):
            unresolved_bits = self._unresolved_bits[:_BITS_PER_SUBFRAME]
            del self._unresolved_bits[:_BITS_PER_SUBFRAME]

            bits = [self._resolve_bit(ub) for ub in unresolved_bits]

    def _determine_bit_phase(self) -> None:
        assert self._bit_phase is None, "The bit phase has already been determined"

        for offset in range(_BITS_PER_SUBFRAME):
            unresolved_bits = self._unresolved_bits[offset:]
            determined = False

            # If each subframe in ``unresolved_bits`` starts with the TLM
            # preamble (or its inverse) then we've found the boundaries between
            # subframes and can determine the overall bit phase.
            #
            # If ``offset`` is non-zero then there's a partial subframe at the
            # start of ``self._unresolved_bits`` which can be discarded.
            if self._all_subframes_start_with_preamble(_TLM_PREAMBLE, unresolved_bits):
                determined = True
                self._bit_phase = 1

            if self._all_subframes_start_with_preamble(
                _INVERSE_TLM_PREAMBLE, unresolved_bits
            ):
                determined = True
                self._bit_phase = -1

            if determined:
                del self._unresolved_bits[:offset]
                logger.info(
                    f"Determined bit phase for satellite {self._satellite_id}: {self._bit_phase}"
                )
                return

    def _all_subframes_start_with_preamble(
        self, preamble: list[UnresolvedBit], unresolved_bits: list[UnresolvedBit]
    ) -> bool:
        """Determines if all subframes in ``unresolved_bits`` start with ``preamble``.

        Assumes the first subframe starts at index 0, the second at 300, etc.
        If the length of ``unresolved_bits`` isn't an integer multiple of
        ``BITS_PER_SUBFRAME`` the leftover bits at the end are ignored.
        """
        assert len(preamble) <= len(
            unresolved_bits
        ), "The preamble must be equal or shorter in length than the unresolved bits"
        assert (
            len(unresolved_bits) >= _BITS_PER_SUBFRAME
        ), "Not enough unresolved bits for a subframe"

        for i in range(
            0, len(unresolved_bits) - (_BITS_PER_SUBFRAME - 1), _BITS_PER_SUBFRAME
        ):
            if not np.array_equal(preamble, unresolved_bits[i : i + len(preamble)]):
                return False

        return True

    def _resolve_bit(self, unresolved_bit: UnresolvedBit) -> Bit:
        assert (
            self._bit_phase is not None
        ), "A bit can't be resolved until the bit phase is determined"

        if self._bit_phase == -1:
            return 1 if unresolved_bit == -1 else 0
        else:
            return 0 if unresolved_bit == -1 else 1