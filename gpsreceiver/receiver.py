import pprint

from .acquirer import Acquirer
from .antenna import Antenna


class Receiver:
    def __init__(self, antenna: Antenna) -> None:
        self._acquirer = Acquirer()
        self._antenna = antenna

    def step_1ms(self) -> None:
        pprint.pp(
            self._acquirer.handle_1ms_of_samples(self._antenna.sample_1ms(), set())
        )
