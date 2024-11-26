from dataclasses import dataclass
from typing import Literal

from .types import Bit


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
