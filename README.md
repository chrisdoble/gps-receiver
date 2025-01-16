This repository contains my software-defined GPS receiver project.

# Features

- Uses the legacy coarse/acquisition (C/A) code to produce clock bias and location estimates.
- Produces estimates in as little as ~24 s from cold start (depending on environmental factors).
- Location estimates tend to be within a few hundred metres of the true location.
- Runs from pre-recorded sample files or a connected RTL-SDR.
- Written in Python with no runtime dependencies other than aiohttp (for the dashboard), NumPy, Pydantic (for data serialisation), and pyrtlsdr.

# Setup

## Hardware

If you'd like to record your own samples or run the receiver in real-time from an [RTL-SDR](https://www.rtl-sdr.com/about-rtl-sdr/), you'll need [a GPS antenna](https://www.sparkfun.com/products/14986) and (optionally) [a ground plate](https://www.sparkfun.com/products/17519). You'll get the best results in large, open areas with a clear view of the sky in all directions, e.g. a park.

## Software

```bash
# gpsreceiver
cd gpsreceiver
python -m venv .env
source .env/bin/activate
pip install -r requirements.txt
```

# Running

## From a file

The file must contain a series of I/Q samples recorded at a rate matching `SAMPLES_PER_MILLISECOND` in `config.py` (the default rate is 2.046 MHz). The samples' I and Q components must be represented by 32-bit floats and be interleaved, i.e.

```
[32-bit float][32-bit float][32-bit float][32-bit float]...
      ^             ^             ^             ^
  Sample 0 I    Sample 0 Q    Sample 1 I    Sample 1 Q
```

You can pass the file to the GPS receiver by running the following from within the `gpsreceiver` directory

```bash
python -m gpsreceiver -f $FILE_PATH -t $START_TIMESTAMP
```

where `$FILE_PATH` is the path to the file and `$START_TIMESTAMP` is the Unix time when the samples began being recorded.

Phillip Tennen made such a file available as part of his [Gypsum](https://github.com/codyd51/gypsum) project. It contains ~13 minutes of samples recorded from [St Ives in the UK](https://maps.app.goo.gl/jbhZ1QGLcfHn7PJA9). To use it:

1. Download `nov_3_time_18_48_st_ives.zip` from [here](https://github.com/codyd51/gypsum/releases/tag/1.0)
2. Unzip it.
3. Run `python -m gpsreceiver -f nov_3_time_18_48_st_ives -t 1699037280`.

If you'd like to record your own file:

1. Connect your antenna to your RTL-SDR and your RTL-SDR to your computer.
2. Install [GNU Radio](https://www.gnuradio.org/).
3. Open the GNU Radio Companion (GNURC) by running `gnuradio-companion`.
4. Open `rtl_srd_gps_sampler.grc` in GNURC.
5. Click play in GNURC. A window will open.
6. Record data for as long as you'd like.
7. Close the window that opened in step 5.
8. There will be a new file called `samples-TIMESTAMP`.
9. Run `python -m gpsreceiver -f samples-TIMESTAMP -t TIMESTAMP`.

## From an RTL-SDR

```bash
python -m gpsreceiver --rtl-sdr
```

# Development

```bash
# gpsreceiver
cd gpsreceiver
make format
make type_check
```
