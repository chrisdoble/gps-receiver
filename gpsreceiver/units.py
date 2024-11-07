# A timestamp in "sample time", i.e. t = 0 s just before the first sample is
# taken and t = 1 s just after config.SAMPLES_PER_SECOND have been taken.
#
# This definition is useful because the receiver's processing rate may be
# different from the sampling rate (e.g. when reading samples from a file) but
# we still want to time some actions relative to the samples rather than the
# system clock (e.g. performing acquisition every x s).
SampleTimestampSeconds = float

# The ID of a GPS satellite based on its PRN signal number. This can be an
# integer between 1 and 32 inclusive, but PRN 1 is not currently in use[1].
#
# 1: https://en.wikipedia.org/wiki/List_of_GPS_satellites#PRN_status_by_satellite_block
SatelliteId = int
