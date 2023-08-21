from typing import Tuple

from model import *


class ServerBoard(Board):
    def checkStatus(self) -> Symbol:
        Vec2 = Tuple[int, int]

        def orientedPass(
            board: Board,
            innerStep: Vec2,
            outerStep: Vec2,
            symbol: Symbol,
            winCount: int,
            start: Position,
        ) -> bool:
            while board.fits(start):
                cur = start.clone()
                cnt = 0
                while board.fits(cur):
                    if board.getSymbol(cur) == symbol:
                        cnt += 1
                    else:
                        cnt = 0
                    if cnt >= winCount:
                        return True
                    cur.addTuple(innerStep)
                start.addTuple(outerStep)
            return False

        winCount = 5
        r = self.getRadius()
        stepTriples = [
            ((1, 0), (0, -1), Position(-r, r)),
            ((0, -1), (1, 0), Position(-r, r)),
            ((-1, -1), (1, 0), Position(-r, r)),
            ((1, -1), (-1, 0), Position(r, r)),
        ]
        for triple in stepTriples:
            if orientedPass(
                self, triple[0], triple[1], Symbol.CROSS, winCount, triple[2]
            ):
                return Symbol.CROSS
            if orientedPass(
                self, triple[0], triple[1], Symbol.NOUGHT, winCount, triple[2]
            ):
                return Symbol.NOUGHT
        return Symbol.BLANK


class ServerGame(Game):
    def __init__(self, players: List[Player], initRadius: int):
        super().__init__(players, initRadius)
        self.board: ServerBoard = self.board  # Trick type system

    def makeBoard(self, initRadius: int):
        return ServerBoard(initRadius)

    def makeMove(self, pos: Position, sym: Symbol) -> MoveError:
        err = super().makeMove(pos, sym)
        if err is MoveError.SUCCESS:
            self.status = self.board.checkStatus()
        return err
