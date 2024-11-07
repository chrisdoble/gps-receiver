from .units import SampleTimestampSeconds, SatelliteId

# Sampling

# A GPS satellite's navigation message (50 bps) is XORed with its PRN
# (1.023 Mbps) and the result is BPSK modulated onto a carrier wave whose
# frequency is 1575.42 MHz. BPSK modulation results in a main lobe with a
# bandwidth equal to twice the data rate - in this case that's 2.046 MHz. That
# means we can capture the majority of the signal power by sampling between
# 1573.374 MHz and 1577.466 MHz.
#
# The Shannon-Nyquist sampling theorem says that, to avoid aliasing, the
# sampling rate must be at least double the highest frequency. In this case that
# would be 3154.932 MHz which is prohibitively high. Instead we can take
# advantage of aliasing and undersample the signal to effectively shift its
# central frequency to 0 Hz. If we sample at 2.046 MHz there will be an alias
# with a central frequency at 0 Hz, effectively removing the carrier frequency.
#
# This sampling rate has the added benefit that the number of samples in 1 ms of
# data is equal to twice the number of chips in a C/A PRN code (1023). So, when
# we're trying to correlate 1 ms of a received signal with a local replica of a
# C/A PRN code we can simply repeat each code chip twice to get a signal of the
# same length. This avoids needing to e.g. pad the local replica with zeroes.
SAMPLES_PER_MILLISECOND: int = 2046
SAMPLES_PER_SECOND = SAMPLES_PER_MILLISECOND * 1000

# Acquisition

# The number of seconds between acquisition attempts.
#
# This value was chosen experimentally to balance the frequency of attempting
# acquisition and the computational cost of doing so.
ACQUISITION_INTERVAL_SECONDS: SampleTimestampSeconds = 10

# An acquisition result must have a strength above this threshold in order to be
# considered successful. Its strength is measured as the peak-to-mean ratio of
# the correlation between the received signal and the local C/A PRN code for a
# particular Doppler shift and all possible C/A PRN code phase shifts.
#
# This value was chosen experimentally.
ACQUISITION_STRENGTH_THRESHOLD: float = 3

# The IDs of all GPS satellites that we may track.
#
# ID 1 isn't included because it's not currently in use[1].
#
# 1: https://en.wikipedia.org/wiki/List_of_GPS_satellites#PRN_status_by_satellite_block
ALL_SATELLITE_IDS: set[SatelliteId] = set(range(2, 33))

# During acquisition we perform both coherent and non-coherent integration over
# multiple 1 ms periods of samples and add the results. This strengthens weak
# signals as would happen if we simply extended the 1 ms period, but minimises
# the issue of navigation bit changes affecting correlation magnitude.
#
# This constant controls how many ms of data to use. Increasing it increases the
# correlation strength, but also makes it more likely we'll see a navigation bit
# change which can negatively affect the carrier wave phase estimate. That's not
# too big of an issue as the tracking loop will eventually find the right value.
MS_OF_SAMPLES_REQUIRED_TO_PERFORM_ACQUISITION: int = 10
