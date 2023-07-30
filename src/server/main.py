import argparse
import sys

from pathlib import Path

sys.path.insert(1, Path(__file__).absolute().parent.parent.as_posix())

from server import ServerGame
from model import Player, Symbol


def main():
    argParser = argparse.ArgumentParser()
    argParser.add_argument("-p1", required=True)
    argParser.add_argument("-p2", required=True)
    args = argParser.parse_args()

    player1 = Player(1, args.p1, Symbol.CROSS)
    player2 = Player(2, args.p2, Symbol.NOUGHT)
    serverGame = ServerGame([player1, player2], 5)


if __name__ == "__main__":
    main()
