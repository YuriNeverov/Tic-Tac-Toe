

from typing import Optional
from model import Game


class ClientProcess:
    def __init__(self):
        self.game: Optional[Game] = None
        