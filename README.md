This repository contains my GPS receiver project.

# Setup

```bash
python -m venv .env
source .env/bin/activate
pip install -r requirements.txt
mkdir data
```

Download `nov_3_time_18_48_st_ives.zip` from [here](https://github.com/codyd51/gypsum/releases/tag/1.0) and unzip it into the `data` directory.

# Development

```bash
# Autoformat
make format

# Type check
make type_check

# Run
python -m gpsreceiver
```