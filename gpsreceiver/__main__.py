import logging
from datetime import datetime, timezone
from pathlib import Path

from .antenna import FileAntenna
from .receiver import Receiver

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO
)

receiver = Receiver(
    FileAntenna(
        Path("data/nov_3_time_18_48_st_ives"),
        datetime(2023, 11, 3, 18, 48, 0, 0, timezone.utc),
    )
)

while True:
    receiver.step_1ms()
