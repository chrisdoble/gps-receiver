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
        Path("data/samples-20241202T044931.3356330000"),
        datetime(2024, 12, 2, 4, 49, 31, 335633, timezone.utc),
    )
)

while True:
    receiver.step_1ms()
