#!/usr/bin/python3

from enum import Enum
from typing import List, Optional, Tuple


class Position:
    def __init__(self, x: int, y: int):
        assert x != 0 and y != 0
        self.x = x
        self.y = y

    def clone(self):
        return Position(self.x, self.y)
    
    def add(self, x: int, y: int):
        self.x += x
        self.y += y

    def addTuple(self, v: Tuple[int, int]):
        assert isinstance(v, tuple) and len(v) == 2
        self.add(v[0], v[1])


class Symbol(Enum):
    BLANK = 0
    CROSS = 1
    NOUGHT = 2


def invertTeam(sym: Symbol):
    if sym == Symbol.CROSS:
        return Symbol.NOUGHT
    if sym == Symbol.NOUGHT:
        return Symbol.CROSS
    return sym


class MoveError(Enum):
    SUCCESS = 0
    WRONG_TEAM = 1
    WRONG_PLACE = 2
    WRONG_SYMBOL = 3
    GAME_ALREADY_OVER = 4


class Player:
    def __init__(self, id: int, name: str, sym: Symbol):
        self.id = id
        self.name = name
        self.sym = sym


class Board:
    __quartersCount = 4
    BoardPosition = (int, int, int)

    def __init__(self, radius: int):
        assert radius > 0
        self.repr: List[List[List[Symbol]]] = [
            [[Symbol.BLANK for _ in range(radius)] for _ in range(radius)]
            for _ in range(Board.__quartersCount)
        ]
        self.__hash = 0

    def getRadius(self):
        return len(self.repr[0])

    """
    \pre: pos = (x, y), x != 0, y != 0
    """

    def getReprIndex(pos: Position) -> "Optional[Board.BoardPosition]":
        if pos.x > 0 and pos.y > 0:
            quarter = 1
        elif pos.x < 0 and pos.y > 0:
            quarter = 2
        elif pos.x < 0 and pos.y < 0:
            quarter = 3
        elif pos.x > 0 and pos.y < 0:
            quarter = 4
        else:
            return None
        return (quarter, abs(pos.x) - 1, abs(pos.y) - 1)

    """
    \pre: radius > getRadius()
    """

    def increaseRadius(self, radius: int):
        oldRadius = self.getRadius()
        if oldRadius >= radius:
            return
        difference = radius - oldRadius
        for q in range(Board.__quartersCount):
            for i in range(oldRadius):
                for _ in range(difference):
                    self.repr[q][i].append(Symbol.BLANK)
            for _ in range(difference):
                self.repr[q].append([Symbol.BLANK for _ in range(radius)])

    @staticmethod
    def hashForPos(pos: "Board.BoardPosition", sym: Symbol):
        return sym * (pos[0] ** 2) * pos[1] * pos[2]

    def setSymbol(self, pos: Position, sym: Symbol):
        q, i, j = self.getReprIndex(pos)
        oldSym = self.repr[q][i][j]
        self._hash ^= Board.hashForPos((q, i, j), oldSym)
        self._hash ^= Board.hashForPos((q, i, j), sym)
        self.repr[q][i][j] = sym

    def getSymbol(self, pos: Position) -> Optional[Symbol]:
        if not self.fits(pos):
            return None
        q, i, j = self.getReprIndex(pos)
        return self.repr[q][i][j]

    def posDifference(self, pos: Position) -> int:
        return max(0, max(abs(pos.x), abs(pos.y)) - self.getRadius())
    
    def fits(self, pos: Position):
        return self.posDifference(pos) > 0

    def makeFit(self, pos: Position):
        self.increaseRadius(self.getRadius() + self.posDifference(pos))

    def hash(self) -> int:
        return self.__hash


class Game:
    def __init__(self, players: List[Player], initRadius: int):
        self.curTeam = Symbol.CROSS
        # self.status is winner team when game is over, Symbol.BLANK otherwise
        self.status = Symbol.BLANK
        self.players = players
        self.board: Board = self.makeBoard(initRadius)
    
    def makeBoard(self, initRadius: int) -> Board:
        return Board(initRadius)

    def makeMove(self, pos: Position, sym: Symbol) -> MoveError:
        if self.status is not Symbol.BLANK:
            return MoveError.GAME_ALREADY_OVER
        if self.curTeam != sym:
            return MoveError.WRONG_TEAM
        self.board.makeFit(pos)
        if self.board.getSymbol(pos) != Symbol.BLANK:
            return MoveError.WRONG_PLACE
        if sym == Symbol.BLANK:
            return MoveError.WRONG_SYMBOL
        self.curTeam = invertTeam(self.curTeam)
        self.board.setSymbol(pos, sym)
        return MoveError.SUCCESS
