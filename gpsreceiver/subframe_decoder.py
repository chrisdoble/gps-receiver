from dataclasses import dataclass
from typing import Literal, cast

from .constants import BITS_PER_SUBFRAME
from .types import Bit
from .utils import InvariantError, invariant

_BITS_PER_WORD = 30

# The first 24 bits in a word are data bits, the following 6 are parity bits.
_DATA_BITS_PER_WORD = 24


@dataclass
class Telemetry:
    """A telemetry (TLM) word.

    See section 20.3.3.1 of IS-GPS-200 for more information.
    """

    # If ``True``, the probability of the error in the GPS signal exceeding its
    # upper bound for more than 5.2 seconds is much lower than if ``False``.
    integrity_status_flag: bool


SubframeId = Literal[1, 2, 3, 4, 5]


@dataclass
class Handover:
    """A handover word (HOW).

    See section 20.3.3.2 of IS-GPS-200 for more information.
    """

    # The time-of-week (TOW) count at the leading edge of the next subframe.
    #
    # The TOW count is a 19 bit value representing the number of X1 epochs
    # (1.5 s periods) that have occurred since the start of the week. This field
    # contains the 17 most significant bits (MSBs) of the TOW count as it will
    # be at the leading edge of the next subframe. With 17 bits we have a
    # granularity of 1.5 s * 2^2 = 6 s which is exactly how long it takes to
    # transmit a subframe. Thus, the two LSBs aren't even necessary!
    tow_count_msbs: list[Bit]

    # If ``True``, the error in the GPS signal may be worse than expected.
    alert_flag: bool

    # If ``True``, the satellite has anti-spoof mode enabled.
    anti_spoof_flag: bool

    subframe_id: SubframeId


@dataclass
class Subframe:
    telemetry: Telemetry
    handover: Handover


@dataclass
class Subframe1(Subframe):
    """Subframe 1.

    See section 20.3.3.3 of IS-GPS-200 for more information.
    """

    # The GPS week number mod 1024.
    #
    # It's mod 1024 because only the 10 LSBs are transmitted.
    #
    # See section 6.2.4 of IS-GPS-200 for more information.
    week_number_mod_1024: int

    # Which codes are commanded on for the in-phase component of the L2 channel.
    codes_on_l2_channel: list[Bit]

    # An index that indicates the expected error in the GPS signal.
    ura_index: int

    # A 6 bit field indicating the health of the satellite's navigation data.
    #
    # If the MSB is 0 the data is healthy, if it's 1 the data is unhealthy in
    # some way. The next 5 bits indicate the health of different components.
    sv_health: list[Bit]

    issue_of_data_clock: list[Bit]
    l2_p_data_flag: Bit

    # The L1-L2 correction term, in seconds.
    t_gd: float

    # The clock data reference time, in seconds.
    t_oc: float

    # In seconds/seconds^2.
    a_f2: float

    # In seconds/second.
    a_f1: float

    # In seconds.
    a_f0: float


@dataclass
class Subframe2(Subframe):
    """Subframe 2.

    See section 20.3.3.4 of IS-GPS-200 for more information.
    """

    issue_of_data_ephemeris: list[Bit]

    # Amplitude of the sine harmonic correction term to the orbit radius, in
    # meters.
    c_rs: float

    # Mean motion difference from computed value, in semi-circles/second.
    delta_n: float

    # Mean anomaly at reference time, in semi-circles.
    m0: float

    # Amplitude of the cosine harmonic correction term to the argument of
    # latitude, in radians.
    c_uc: float

    # Eccentricity (dimensionless).
    e: float

    # Amplitude of the sine harmonic correction term to the argument of
    # latitude, in radians.
    c_us: float

    # Square root of the semi-major axis, in √meters.
    sqrt_a: float

    # Reference time ephemeris, in seconds.
    t_oe: float

    fit_interval_flag: Bit
    age_of_data_offset: list[Bit]


@dataclass
class Subframe3(Subframe):
    """Subframe 3.

    See section 20.3.3.4 of IS-GPS-200 for more information.
    """

    # Amplitude of the cosine harmonic correction term to the angle of
    # inclination, in radians.
    c_ic: float

    # Longitude of ascending node of orbit plane at weekly epoch, in
    # semi-circles.
    omega_0: float

    # Amplitude of the sine harmonic correction term to the angle of
    # inclination, in radians.
    c_is: float

    # Inclination angle at reference time, in semi-circles.
    i_0: float

    # Amplitude of the cosine harmonic correction term to the orbit radius, in
    # meters.
    c_rc: float

    # Argument of perigee, in semi-circles.
    omega: float

    # Rate of right ascension, in semi-circles/second.
    omega_dot: float

    issue_of_data_ephemeris: list[Bit]

    # Rate of inclination angle, in semi-circles/second.
    idot: float


@dataclass
class Subframe4(Subframe):
    """Subframe 4.

    See section 20.3.3.5 of IS-GPS-200 for more information.
    """

    # We don't need anything from subframe 4 other than the TOW count.
    pass


@dataclass
class Subframe5(Subframe):
    """Subframe 5.

    See section 20.3.3.5 of IS-GPS-200 for more information.
    """

    # We don't need anything from subframe 5 other than the TOW count.
    pass


class SubframeDecoder:
    """Decodes subframes.

    This class takes subframe ``Bit``s from a ``BitIntegrator``, decodes them
    into instances of data classes, and forwards them to a ``WorldModel``.
    """

    def handle_bits(self, bits: list[Bit]) -> None:
        print(_SubframeDecoder(bits).decode())


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
        telemetry = self._decode_telemetry()
        handover = self._decode_handover()

        match handover.subframe_id:
            case 1:
                return self._decode_subframe_1(telemetry, handover)

            case 2:
                return self._decode_subframe_2(telemetry, handover)

            case 3:
                return self._decode_subframe_3(telemetry, handover)

            case 4:
                return self._decode_subframe_4(telemetry, handover)

            case 5:
                return self._decode_subframe_5(telemetry, handover)

            case _:
                raise InvariantError(f"Invalid subframe ID: {handover.subframe_id}")

    def _decode_telemetry(self) -> Telemetry:
        # The preamble is fixed.
        preamble = self._get_bits(8)
        invariant(preamble == [1, 0, 0, 0, 1, 0, 1, 1], "Invalid TLM preamble")

        # The TLM message contains information needed for the precise
        # positioning service. We can't use that, so ignore it.
        self._skip_bits(14)

        integrity_status_flag = self._get_bool()

        # The last data bit is reserved.
        self._skip_bits(1)

        return Telemetry(integrity_status_flag)

    def _decode_handover(self) -> Handover:
        tow_count_msbs = self._get_bits(17)
        alert_flag = self._get_bool()
        anti_spoof_flag = self._get_bool()

        # A subframe ID may only be 1 through 5, inclusive.
        subframe_id = self._get_int(3)
        invariant(subframe_id in [1, 2, 3, 4, 5], f"Invalid subframe ID: {subframe_id}")

        # Parity
        self._skip_bits(2)

        return Handover(
            tow_count_msbs, alert_flag, anti_spoof_flag, cast(SubframeId, subframe_id)
        )

    def _decode_subframe_1(self, telemetry: Telemetry, handover: Handover) -> Subframe1:
        week_number_mod_1024 = self._get_int(10)
        codes_on_l2_channel = self._get_bits(2)
        ura_index = self._get_int(4)
        sv_health = self._get_bits(6)
        issue_of_data_clock_msbs = self._get_bits(2)
        l2_p_data_flag = self._get_bit()

        # Reserved
        self._skip_bits(87)

        t_gd = self._get_float(8, -31, True)
        issue_of_data_clock_lsbs = self._get_bits(8)
        issue_of_data_clock = issue_of_data_clock_msbs + issue_of_data_clock_lsbs
        t_oc = self._get_float(16, 4, False)
        a_f2 = self._get_float(8, -55, True)
        a_f1 = self._get_float(16, -43, True)
        a_f0 = self._get_float(22, -31, True)

        # Parity
        self._skip_bits(2)

        return Subframe1(
            telemetry,
            handover,
            week_number_mod_1024,
            codes_on_l2_channel,
            ura_index,
            sv_health,
            issue_of_data_clock,
            l2_p_data_flag,
            t_gd,
            t_oc,
            a_f2,
            a_f1,
            a_f0,
        )

    def _decode_subframe_2(self, telemetry: Telemetry, handover: Handover) -> Subframe2:
        issue_of_data_ephemeris = self._get_bits(8)
        c_rs = self._get_float(16, -5, True)
        delta_n = self._get_float(16, -43, True)
        m0 = self._get_float(32, -31, True)
        c_uc = self._get_float(16, -29, True)
        e = self._get_float(32, -33, False)
        c_us = self._get_float(16, -29, True)
        sqrt_a = self._get_float(32, -19, False)
        t_oe = self._get_float(16, 4, False)
        fit_interval_flag = self._get_bit()
        age_of_data_offset = self._get_bits(5)

        # Parity
        self._skip_bits(2)

        return Subframe2(
            telemetry,
            handover,
            issue_of_data_ephemeris,
            c_rs,
            delta_n,
            m0,
            c_uc,
            e,
            c_us,
            sqrt_a,
            t_oe,
            fit_interval_flag,
            age_of_data_offset,
        )

    def _decode_subframe_3(self, telemetry: Telemetry, handover: Handover) -> Subframe3:
        c_ic = self._get_float(16, -29, True)
        omega_0 = self._get_float(32, -31, True)
        c_is = self._get_float(16, -29, True)
        i_0 = self._get_float(32, -31, True)
        c_rc = self._get_float(16, -5, True)
        omega = self._get_float(32, -31, True)
        omega_dot = self._get_float(24, -43, True)
        issue_of_data_ephemeris = self._get_bits(8)
        idot = self._get_float(14, -43, True)

        # Parity
        self._skip_bits(2)

        return Subframe3(
            telemetry,
            handover,
            c_ic,
            omega_0,
            c_is,
            i_0,
            c_rc,
            omega,
            omega_dot,
            issue_of_data_ephemeris,
            idot,
        )

    def _decode_subframe_4(self, telemetry: Telemetry, handover: Handover) -> Subframe4:
        # We don't need anything from subframe 4 other than the TOW count.
        return Subframe4(telemetry, handover)

    def _decode_subframe_5(self, telemetry: Telemetry, handover: Handover) -> Subframe5:
        # We don't need anything from subframe 5 other than the TOW count.
        return Subframe5(telemetry, handover)

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
        bits = self._get_bits(bit_count)
        bit_string = "".join([str(b) for b in bits])
        return int(bit_string, 2)

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
