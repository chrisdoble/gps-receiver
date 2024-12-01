This repository contains my GPS receiver project.

# Setup and running

```bash
python -m venv .env
source .env/bin/activate
pip install -r requirements.txt
mkdir data
```

If you'd like to use pre-recorded signal data, Phillip Tennen recorded around 13 minutes of data from [St Ives in the UK](https://maps.app.goo.gl/jbhZ1QGLcfHn7PJA9) for his [Gypsum](https://github.com/codyd51/gypsum) project. To use it:

1. Download  `nov_3_time_18_48_st_ives.zip` from [here](https://github.com/codyd51/gypsum/releases/tag/1.0).
2. Unzip it into the `data` directory.
3. Update `__main__.py` to pass the path `data/nov_3_time_18_48_st_ives` and the timestamp `datetime(2023, 11, 3, 18, 48, 0, 0, timezone.utc)` to the `FileAntenna` constructor.

If you'd like to record your own data using an [RTL-SDR](https://www.rtl-sdr.com/):

1. Install [GNU Radio](https://www.gnuradio.org/).
2. Open the GNU Radio Companion (GNURC) by running `gnuradio-companion` in a terminal.
3. Open `rtl_srd_gps_sampler.grc` in GNURC.
4. Connect a GPS antenna to your RTL-SDR and your RTL-SDR to your computer.
5. Click play in GNURC. A window will open.
6. Record data for as long as you'd like.
7. Close the window.
8. There will be a new file in the `data` directory called `samples-TIMESTAMP`.
8. Update `__main__.py` to pass the path of the newly created file and the timestamp found in the filename.

To start the GPS receiver, run `python -m gpsreceiver` from the root of the repository.

# Development

```bash
# Autoformat
make format

# Type check
make type_check
```
