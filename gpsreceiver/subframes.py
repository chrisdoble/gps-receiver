from dataclasses import dataclass
from typing import Literal

from .types import Bit

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

    subframe_id: SubframeId


@dataclass
class Subframe:
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

    # A 6 bit field indicating the health of the satellite's navigation data.
    #
    # If the MSB is 0 the data is healthy, if it's 1 the data is unhealthy in
    # some way. The next 5 bits indicate the health of different components.
    sv_health: list[Bit]

    t_gd: float  # seconds
    t_oc: float  # seconds
    a_f2: float  # seconds/second^2
    a_f1: float  # seconds/second
    a_f0: float  # seconds


@dataclass
class Subframe2(Subframe):
    """Subframe 2.

    See section 20.3.3.4 of IS-GPS-200 for more information.
    """

    c_rs: float  # meters
    delta_n: float  # semi-circles/second
    m_0: float  # semi-circles
    c_uc: float  # radians
    e: float  # dimensionless
    c_us: float  # radians
    sqrt_a: float  # √meters
    t_oe: float  # seconds


@dataclass
class Subframe3(Subframe):
    """Subframe 3.

    See section 20.3.3.4 of IS-GPS-200 for more information.
    """

    c_ic: float  # radians
    omega_0: float  # semi-circles
    c_is: float  # radians
    i_0: float  # semi-circles
    c_rc: float  # meters
    omega: float  # semi-circles
    omega_dot: float  # semi-circles/second
    i_dot: float  # semi-circles/second


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
