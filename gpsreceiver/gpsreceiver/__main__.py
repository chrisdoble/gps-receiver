import logging
from argparse import ArgumentParser
from datetime import datetime, timezone
from pathlib import Path

from .acquirer import MainProcessAcquirer, SubprocessAcquirer
from .antenna import FileAntenna, RtlSdrAntenna
from .receiver import Receiver

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO
)

argument_parser = ArgumentParser()
argument_parser.add_argument("-f", "--file", help="the path to the input file to use")
argument_parser.add_argument(
    "-t", "--time", help="the start time of the input file, in Unix time"
)
argument_parser.add_argument(
    "--rtl-sdr", action="store_true", help="run in real time from an RTL-SDR"
)
args = argument_parser.parse_args()

try:
    if args.file and args.time:
        FileAntenna(
            Path(args.file),
            Receiver(MainProcessAcquirer()),
            datetime.fromtimestamp(float(args.time), tz=timezone.utc),
        ).start()
    elif args.rtl_sdr:
        RtlSdrAntenna(Receiver(SubprocessAcquirer())).start()
    else:
        argument_parser.print_help()
except KeyboardInterrupt:
    pass
