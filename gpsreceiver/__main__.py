from pathlib import Path

from .antenna import FileAntenna
from .receiver import Receiver

receiver = Receiver(FileAntenna(Path("data/nov_3_time_18_48_st_ives")))

while True:
    receiver.step_1ms()
