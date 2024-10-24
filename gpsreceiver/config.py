# Sampling rates
#
# A GPS satellite's navigation message (50 bps) is XORed with its C/A PRN code
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
SAMPLES_PER_MILLISECOND: int = 2046
SAMPLES_PER_SECOND = SAMPLES_PER_MILLISECOND * 1000
