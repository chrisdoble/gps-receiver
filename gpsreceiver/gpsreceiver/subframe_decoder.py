import logging
from typing import cast

from .constants import BITS_PER_SUBFRAME
from .subframes import (
    Handover,
    Subframe,
    Subframe1,
    Subframe2,
    Subframe3,
    Subframe4,
    Subframe5,
    SubframeId,
)
from .types import Bit, SatelliteId
from .utils import InvariantError, invariant, parse_int_from_bits
from .world import World

_BITS_PER_WORD = 30

# The first 24 bits in a word are data bits, the following 6 are parity bits.
_DATA_BITS_PER_WORD = 24


logger = logging.getLogger(__name__)


class SubframeDecoder:
    """Decodes subframes.

    This class takes subframe ``Bit``s from a ``PseudobitIntegrator``, decodes
    them into instances of data classes, and forwards them to the ``World``.
    """

    def __init__(self, satellite_id: SatelliteId, world: World) -> None:
        # The number of subframes that have been decoded.
        self._count = 0

        self._satellite_id = satellite_id
        self._world = world

    @property
    def count(self) -> int:
        return self._count

    def handle_bits(self, bits: list[Bit]) -> None:
        subframe = _SubframeDecoder(bits).decode()
        logger.info(
            f"[{self._satellite_id}] Decoded subframe {subframe.handover.subframe_id}"
        )
        self._count += 1
        self._world.handle_subframe(self._satellite_id, subframe)


class _SubframeDecoder:
    """Implements the decoding logic.

    This is separate from ``SubframeDecoder`` because decoding requires some
    state and it's easier to create and discard an instance of this class for
    each subframe than ensure we reset state appropriately for each subframe.
    """

    def __init__(self, transmitted: list[Bit]) -> None:
        self._cursor = 0
        self._data = _decode_subframe_data(transmitted)

    def decode(self) -> Subframe:
        self._decode_telemetry()

        handover = self._decode_handover()
        match handover.subframe_id:
            case 1:
                return self._decode_subframe_1(handover)

            case 2:
                return self._decode_subframe_2(handover)

            case 3:
                return self._decode_subframe_3(handover)

            case 4:
                return self._decode_subframe_4(handover)

            case 5:
                return self._decode_subframe_5(handover)

            case _:
                raise InvariantError(f"Invalid subframe ID: {handover.subframe_id}")

    def _decode_telemetry(self) -> None:
        # We don't need anything from the TLM word so nothing is returned from
        # this method, but we still need to parse it to move the cursor past.

        # The preamble is fixed.
        preamble = self._get_bits(8)
        invariant(preamble == [1, 0, 0, 0, 1, 0, 1, 1], "Invalid TLM preamble")

        # The TLM message contains information needed for the precise
        # positioning service. We can't use that, so ignore it.
        self._skip_bits(14)

        # Integrity status flag.
        self._get_bit()

        # The last data bit is reserved.
        self._skip_bits(1)

    def _decode_handover(self) -> Handover:
        tow_count_msbs = self._get_bits(17)

        # Alert flag.
        self._get_bit()

        # Anti-spoof flag.
        self._get_bit()

        # A subframe ID may only be 1 through 5, inclusive.
        subframe_id = self._get_int(3)
        invariant(subframe_id in [1, 2, 3, 4, 5], f"Invalid subframe ID: {subframe_id}")

        # Parity bits.
        self._skip_bits(2)

        return Handover(tow_count_msbs, cast(SubframeId, subframe_id))

    def _decode_subframe_1(self, handover: Handover) -> Subframe1:
        # GPS week number mod 1024.
        self._get_int(10)

        # Code(s) on L2 channel.
        self._get_bits(2)

        # URA index.
        self._get_bits(4)

        sv_health = self._get_bits(6)

        # Issue of data, clock (IODC) MSBs.
        self._get_bits(2)

        # Data flag for L2 P-Code.
        self._get_bit()

        # Reserved.
        self._skip_bits(87)

        t_gd = self._get_float(8, -31, True)

        # IODC LSBs.
        self._get_bits(8)

        t_oc = self._get_float(16, 4, False)
        a_f2 = self._get_float(8, -55, True)
        a_f1 = self._get_float(16, -43, True)
        a_f0 = self._get_float(22, -31, True)

        # Parity bits.
        self._skip_bits(2)

        return Subframe1(
            handover,
            sv_health,
            t_gd,
            t_oc,
            a_f2,
            a_f1,
            a_f0,
        )

    def _decode_subframe_2(self, handover: Handover) -> Subframe2:
        # Issue of data (ephemeris).
        self._get_bits(8)

        c_rs = self._get_float(16, -5, True)
        delta_n = self._get_float(16, -43, True)
        m_0 = self._get_float(32, -31, True)
        c_uc = self._get_float(16, -29, True)
        e = self._get_float(32, -33, False)
        c_us = self._get_float(16, -29, True)
        sqrt_a = self._get_float(32, -19, False)
        t_oe = self._get_float(16, 4, False)

        # Fit interval flag.
        self._get_bit()

        # Age of data offset.
        self._get_bits(5)

        # Parity bits.
        self._skip_bits(2)

        return Subframe2(
            handover,
            c_rs,
            delta_n,
            m_0,
            c_uc,
            e,
            c_us,
            sqrt_a,
            t_oe,
        )

    def _decode_subframe_3(self, handover: Handover) -> Subframe3:
        c_ic = self._get_float(16, -29, True)
        omega_0 = self._get_float(32, -31, True)
        c_is = self._get_float(16, -29, True)
        i_0 = self._get_float(32, -31, True)
        c_rc = self._get_float(16, -5, True)
        omega = self._get_float(32, -31, True)
        omega_dot = self._get_float(24, -43, True)

        # Issue of data (ephemeris).
        self._get_bits(8)

        i_dot = self._get_float(14, -43, True)

        # Parity bits.
        self._skip_bits(2)

        return Subframe3(
            handover,
            c_ic,
            omega_0,
            c_is,
            i_0,
            c_rc,
            omega,
            omega_dot,
            i_dot,
        )

    def _decode_subframe_4(self, handover: Handover) -> Subframe4:
        # We don't need anything from subframe 4 other than the TOW count.
        return Subframe4(handover)

    def _decode_subframe_5(self, handover: Handover) -> Subframe5:
        # We don't need anything from subframe 5 other than the TOW count.
        return Subframe5(handover)

    def _get_bit(self) -> Bit:
        [bit] = self._get_bits(1)
        return bit

    def _get_bits(self, bit_count: int) -> list[Bit]:
        invariant(
            self._cursor + bit_count <= len(self._data),
            "Can't read past end of subframe",
        )

        bits = self._data[self._cursor : self._cursor + bit_count]
        self._cursor += bit_count
        return bits

    def _get_bool(self) -> bool:
        return self._get_bit() == 1

    def _get_float(
        self, bit_count: int, scale_factor_exponent: int, twos_complement: bool
    ) -> float:
        """Reads ``bit_count`` bits as an integer, optionally interprets it in
        two's complement representation, multiplies it by 2 to the power of
        ``scale_factor_exponent``, and returns the result as a ``float``.
        """
        number = self._get_int(bit_count)

        # If we're to interpret the number in two's complement representation
        # and the most significant bit is 1, convert it to a negative number.
        if twos_complement and number & (1 << (bit_count - 1)):
            number -= 1 << bit_count

        return number * 2**scale_factor_exponent

    def _get_int(self, bit_count: int) -> int:
        return parse_int_from_bits(self._get_bits(bit_count))

    def _skip_bits(self, bit_count: int) -> None:
        self._get_bits(bit_count)


def _decode_subframe_data(subframe_transmitted: list[Bit]) -> list[Bit]:
    """Decodes a subframe's data bits from its transmitted bits.

    As per section 20.3.5 of IS-GPS-200, a subframe's source data bits are
    transformed before transmission. This function takes the transmitted bits
    and attempts to decode the source data bits, checking parity in the process.
    Raises a ``ParityError`` if any parity checks fail.

    Parity bits aren't included in the returned value. This means that the input
    list has a length of 300 but the output list has a length of 240.
    """

    # Decoding the data bits is quite simple. A subframe contains 10 words and
    # each word contains 30 bits. The first 24 bits of each word are data bits
    # and the following 6 bits are parity bits. Each data bit has been XORed
    # with bit 30 of the previous word. To undo this we just XOR it again.
    #
    # Checking the parity bits is also reasonably straightforward. Table 20-XIV
    # of IS-GPS-200 lists how each parity bit is computed using either bit 29 or
    # 30 from the previous word and a subset of the data bits. We perform the
    # same computations and ensure they equal what was transmitted.

    invariant(
        len(subframe_transmitted) == BITS_PER_SUBFRAME,
        f"Invalid number of bits to decode subframe. Expected 300, got: {len(subframe_transmitted)}",
    )

    subframe_data: list[Bit] = []

    # For the first word we assume bits 29 and 30 of the "previous word" are 0.
    last_word_bit_29: Bit = 0
    last_word_bit_30: Bit = 0

    for i in range(0, BITS_PER_SUBFRAME, _BITS_PER_WORD):
        word_transmitted = subframe_transmitted[i : i + _BITS_PER_WORD]
        word_data: list[Bit] = []

        for j in range(_DATA_BITS_PER_WORD):
            word_data.append(cast(Bit, word_transmitted[j] ^ last_word_bit_30))

        _verify_parity(
            word_transmitted[24],
            last_word_bit_29,
            word_data,
            [1, 2, 3, 5, 6, 10, 11, 12, 13, 14, 17, 18, 20, 23],
        )

        _verify_parity(
            word_transmitted[25],
            last_word_bit_30,
            word_data,
            [2, 3, 4, 6, 7, 11, 12, 13, 14, 15, 18, 19, 21, 24],
        )

        _verify_parity(
            word_transmitted[26],
            last_word_bit_29,
            word_data,
            [1, 3, 4, 5, 7, 8, 12, 13, 14, 15, 16, 19, 20, 22],
        )

        _verify_parity(
            word_transmitted[27],
            last_word_bit_30,
            word_data,
            [2, 4, 5, 6, 8, 9, 13, 14, 15, 16, 17, 20, 21, 23],
        )

        _verify_parity(
            word_transmitted[28],
            last_word_bit_30,
            word_data,
            [1, 3, 5, 6, 7, 9, 10, 14, 15, 16, 17, 18, 21, 22, 24],
        )

        _verify_parity(
            word_transmitted[29],
            last_word_bit_29,
            word_data,
            [3, 5, 6, 8, 9, 10, 11, 13, 15, 19, 22, 23, 24],
        )

        subframe_data += word_data
        last_word_bit_29 = word_transmitted[28]
        last_word_bit_30 = word_transmitted[29]

    return subframe_data


class ParityError(Exception):
    """Indicates that one or more parity bits in a subframe were invalid."""

    pass


def _verify_parity(
    transmitted_parity: Bit,
    previous_word_parity: Bit,
    word_data: list[Bit],
    word_data_indices: list[int],
) -> None:
    """Uses an equation from table 20-XIV of IS-GPS-200 to compute a parity bit
    and asserts that the computed value equals the transmitted value.

    Raises a ``ParityError`` if the values aren't equal.

    ``word_data_indices`` are 1-based to match the definitions in the table.
    """

    computed_parity: Bit = cast(
        Bit,
        (previous_word_parity + sum([word_data[i - 1] for i in word_data_indices])) % 2,
    )

    if computed_parity != transmitted_parity:
        raise ParityError()
