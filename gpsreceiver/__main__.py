import logging
from pathlib import Path

from .antenna import FileAntenna
from .receiver import Receiver

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO
)

receiver = Receiver(FileAntenna(Path("data/nov_3_time_18_48_st_ives")))

while True:
    receiver.step_1ms()
