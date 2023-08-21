import asyncio

from enum import IntEnum
from math import isqrt
from typing import Any, List, Optional, Tuple


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


class Symbol(IntEnum):
    BLANK = 0
    CROSS = 1
    NOUGHT = 2


def invertTeam(sym: Symbol):
    if sym == Symbol.CROSS:
        return Symbol.NOUGHT
    if sym == Symbol.NOUGHT:
        return Symbol.CROSS
    return sym


class MoveError(IntEnum):
    SUCCESS = 0
    WRONG_TEAM = 1
    WRONG_PLACE = 2
    WRONG_SYMBOL = 3
    GAME_ALREADY_OVER = 4


class ProcessResponseError(IntEnum):
    SUCCESS = 0
    COOKIE_NOT_FOUND = 1
    GAME_NOT_FOUND = 2
    PLAYER_NOT_IN_GAME = 3
    ALREADY_IN_USE = 4
    OVERLOADED = 5


class ServerResponseError(IntEnum):
    SUCCESS = 0
    BAD_REQUEST = 1
    TIMED_OUT = 2
    FORBIDDEN = 3
    INVALID_ANSWER = 4


class Player:
    def __init__(self, id: int, name: str, sym: Symbol = Symbol.BLANK):
        self.id = id
        self.gameId = -1
        self.name = name
        self.sym = sym


class ByteView:
    def __init__(self, array: bytearray, shift: int = 0) -> None:
        self.array = array
        self.shift = shift

    def getFirst(self, n: int) -> bytearray:
        return self.array[self.shift : self.shift + n]

    def takeFirst(self, n: int) -> bytearray:
        res = self.getFirst(n)
        self.shift += n
        return res

    def takeIntFromFirst(self, n: int) -> int:
        return int().from_bytes(self.takeFirst(n), byteorder="big")


class Board:
    __quartersCount = 4
    BoardPosition = Tuple[int, int, int]

    def __init__(self, radius: int):
        assert radius > 0
        self.repr: List[List[List[Symbol]]] = [
            [[Symbol.BLANK for _ in range(radius)] for _ in range(radius)]
            for _ in range(Board.__quartersCount)
        ]
        self.__hash: int = 0

    def getRadius(self):
        return len(self.repr[0])

    """
    @pre: pos = (x, y), x != 0, y != 0
    """

    @staticmethod
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
    @pre: radius > getRadius()
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
    def hashForPos(pos: "Board.BoardPosition", sym: Symbol) -> int:
        return sym * (pos[0] ** 2) * pos[1] * pos[2]

    def setSymbol(self, pos: Position, sym: Symbol):
        triple = self.getReprIndex(pos)
        if triple is None:
            return
        q, i, j = triple
        oldSym = self.repr[q][i][j]
        self.__hash ^= Board.hashForPos((q, i, j), oldSym)
        self.__hash ^= Board.hashForPos((q, i, j), sym)
        self.repr[q][i][j] = sym

    def getSymbol(self, pos: Position) -> Optional[Symbol]:
        if not self.fits(pos):
            return None
        triple = self.getReprIndex(pos)
        if triple is None:
            return
        q, i, j = triple
        return self.repr[q][i][j]

    def posDifference(self, pos: Position) -> int:
        return max(0, max(abs(pos.x), abs(pos.y)) - self.getRadius())

    def fits(self, pos: Position):
        return self.posDifference(pos) > 0

    def makeFit(self, pos: Position):
        self.increaseRadius(self.getRadius() + self.posDifference(pos))

    def hash(self) -> int:
        return self.__hash

    def dumpByteRepr(self, out: bytearray) -> int:
        reprLen = (2 * self.getRadius()) ** 2
        for q in range(Board.__quartersCount):
            for i in range(self.getRadius()):
                for j in range(self.getRadius()):
                    out.extend(int(self.repr[q][i][j]).to_bytes(1, byteorder="big"))
        return reprLen

    def loadByteRepr(self, buffer: bytearray):
        self.increaseRadius(isqrt(len(buffer)) // 2)
        it = 0
        for q in range(Board.__quartersCount):
            for i in range(self.getRadius()):
                for j in range(self.getRadius()):
                    self.repr[q][i][j] = Symbol(buffer[it])
                    it += 1


class Game:
    def __init__(self, players: List[Player], initRadius: int):
        self.curTeam = Symbol.CROSS
        # self.status is winner team when game is over, Symbol.BLANK otherwise
        self.status = Symbol.BLANK
        # Refers Player (Owned by GameProcess)
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


GameId = int
Cookie = bytearray


class Requests(IntEnum):
    InitializeConnection = 0
    MakeGame = 1
    JoinGame = 2
    MakeMove = 3
    GameStatus = 4
    LoadBoard = 5


class InitializeConnectionRequest:
    def __init__(self, name: str):
        self.requestType = Requests.InitializeConnection
        self.name = name

    def serializeInto(self, res: bytearray) -> bytearray:
        bytes = bytearray(self.name.encode("utf-8"))
        Protocol.writePayloadLength(res, len(bytes))
        return Protocol.writeByteArray(res, bytes)

    @staticmethod
    def deserializeFrom(
        array: ByteView, length: int
    ) -> "Optional[InitializeConnectionRequest]":
        if length <= 0:
            return None
        name = array.takeFirst(length).decode("utf-8")
        return InitializeConnectionRequest(name)


class InitializeConnectionResponse:
    def __init__(self, verdict: ProcessResponseError, cookie: Optional[Cookie] = None):
        self.verdict = verdict
        self.cookie = cookie

    def serializeInto(self, res: bytearray) -> bytearray:
        cookieLen = len(self.cookie) if self.cookie else 0
        Protocol.writePayloadLength(res, 2 + cookieLen)
        Protocol.writeInt2(res, self.verdict)
        if self.cookie:
            Protocol.writeByteArray(res, self.cookie)
        return res

    @staticmethod
    def deserializeFrom(array: ByteView, length: int) -> "InitializeConnectionResponse":
        verdict = ProcessResponseError(array.takeIntFromFirst(2))
        cookie = array.takeFirst(length - 2)
        return InitializeConnectionResponse(verdict, cookie)


class MakeGameRequest:
    def __init__(self, initRadius: int):
        self.requestType = Requests.MakeGame
        self.initRadius = initRadius

    def serializeInto(self, res: bytearray) -> bytearray:
        Protocol.writePayloadLength(res, 2)
        return Protocol.writeInt2(res, self.initRadius)

    @staticmethod
    def deserializeFrom(array: ByteView, length: int) -> "Optional[MakeGameRequest]":
        if length != 2:
            return None
        initRadius = array.takeIntFromFirst(length)
        return MakeGameRequest(initRadius)


class MakeGameResponse:
    def __init__(self, verdict: ProcessResponseError, gameId: Optional[GameId] = None):
        self.verdict = verdict
        self.gameId = gameId

    def serializeInto(self, res: bytearray) -> bytearray:
        gameIdBytes = Protocol.getByteArrayForInt(self.gameId) if self.gameId else bytearray()
        Protocol.writePayloadLength(res, 2 + len(gameIdBytes))
        Protocol.writeInt2(res, self.verdict)
        return Protocol.writeByteArray(res, gameIdBytes)

    @staticmethod
    def deserializeFrom(array: ByteView, length: int) -> "MakeGameResponse":
        verdict = ProcessResponseError(array.takeIntFromFirst(2))
        gameId = array.takeIntFromFirst(length - 2)
        return MakeGameResponse(verdict, gameId)


class JoinGameRequest:
    def __init__(self, cookie: Cookie, gameId: GameId, symbol: Symbol):
        self.requestType = Requests.JoinGame
        self.cookie = cookie
        self.gameId = gameId
        self.symbol = symbol

    def serializeInto(self, res: bytearray) -> bytearray:
        cookieLen = len(self.cookie)
        gameIdBytes = Protocol.getByteArrayForInt(self.gameId)
        gameIdLen = len(gameIdBytes)
        Protocol.writePayloadLength(res, 2 + cookieLen + 2 + gameIdLen + 2)
        Protocol.writeInt2(res, cookieLen)
        Protocol.writeByteArray(res, self.cookie)
        Protocol.writeInt2(res, gameIdLen)
        Protocol.writeByteArray(res, gameIdBytes)
        return Protocol.writeInt2(res, self.symbol)

    @staticmethod
    def deserializeFrom(array: ByteView, length: int) -> "Optional[JoinGameRequest]":
        if length < 2:
            return None
        cookieLen = array.takeIntFromFirst(2)
        length -= 2
        if length < cookieLen:
            return None
        cookie = array.takeFirst(cookieLen)
        length -= cookieLen
        if length < 2:
            return None
        gameIdLen = array.takeIntFromFirst(2)
        length -= 2
        if length < gameIdLen:
            return None
        gameId = array.takeIntFromFirst(gameIdLen)
        length -= gameIdLen
        if length != 2:
            return None
        symbol = Symbol(array.takeIntFromFirst(2))
        return JoinGameRequest(cookie, gameId, symbol)


class JoinGameResponse:
    def __init__(
        self,
        verdict: ProcessResponseError,
        board: Optional[bytearray] = None,
        chosenSymbol: Optional[Symbol] = None,
    ):
        self.verdict = verdict
        self.board = board
        self.chosenSymbol = chosenSymbol

    def serializeInto(self, res: bytearray) -> bytearray:
        reprLen = len(self.board) if self.board else 0
        symbolLen = 1 if self.chosenSymbol else 0
        Protocol.writePayloadLength(res, 2 + reprLen + symbolLen)
        Protocol.writeInt2(res, self.verdict)
        if reprLen > 0 and symbolLen > 0:
            assert self.board
            Protocol.writeByteArray(res, self.board)
            Protocol.writeInt1(res, self.chosenSymbol)
        return res

    @staticmethod
    def deserializeFrom(array: ByteView, length: int) -> "JoinGameResponse":
        verdict = ProcessResponseError(array.takeIntFromFirst(2))
        if verdict is not ProcessResponseError.SUCCESS:
            array.takeFirst(length - 2)
            return JoinGameResponse(verdict)
        board = array.takeFirst(length - 2 - 1)
        chosenSymbol = Symbol(array.takeIntFromFirst(1))
        return JoinGameResponse(verdict, board, chosenSymbol)


class MakeMoveRequest:
    def __init__(self, cookie: Cookie, position: Position):
        self.requestType = Requests.MakeMove
        self.cookie = cookie
        self.position = position

    def serializeInto(self, res: bytearray) -> bytearray:
        cookieLen = len(self.cookie)
        Protocol.writePayloadLength(res, 2 + cookieLen + 4 + 4)
        Protocol.writeInt2(res, cookieLen)
        Protocol.writeByteArray(res, self.cookie)
        Protocol.writeInt4(res, self.position.x)
        Protocol.writeInt4(res, self.position.y)
        return res

    @staticmethod
    def deserializeFrom(array: ByteView, length: int) -> "Optional[MakeMoveRequest]":
        if length < 2:
            return None
        cookieLen = array.takeIntFromFirst(2)
        length -= 2
        if length < cookieLen:
            return None
        cookie = array.takeFirst(cookieLen)
        length -= cookieLen
        if length < 4:
            return None
        x = array.takeIntFromFirst(4)
        length -= 4
        if length != 4:
            return None
        y = array.takeIntFromFirst(4)
        return MakeMoveRequest(cookie, Position(x, y))


class MakeMoveResponse:
    def __init__(
        self,
        verdict: ProcessResponseError | MoveError,
        hash: Optional[int] = None,
        status: Optional[Symbol] = None,
    ):
        self.verdict = verdict
        self.hash = hash
        self.status = status

    def serializeInto(self, res: bytearray) -> bytearray:
        Protocol.writePayloadLength(res, 1 + 2 + 8 + 1)
        Protocol.writeInt1(
            res, 0 if isinstance(self.verdict, ProcessResponseError) else 1
        )
        Protocol.writeInt2(res, self.verdict)
        Protocol.writeInt8(res, self.hash if self.hash else 0)
        return Protocol.writeInt1(res, self.status if self.status else 0)

    @staticmethod
    def deserializeFrom(array: ByteView, _: int) -> "MakeMoveResponse":
        errorType = array.takeIntFromFirst(1)
        errorConstructor = ProcessResponseError if errorType == 0 else MoveError
        verdict = errorConstructor(array.takeIntFromFirst(2))
        if int(verdict) != 0:
            array.takeFirst(8 + 1)
            return MakeMoveResponse(verdict)
        hash = array.takeIntFromFirst(8)
        status = Symbol(array.takeIntFromFirst(1))
        return MakeMoveResponse(verdict, hash, status)


class GameStatusRequest:
    def __init__(self, cookie: Cookie):
        self.requestType = Requests.GameStatus
        self.cookie = cookie

    def serializeInto(self, res: bytearray) -> bytearray:
        cookieLen = len(self.cookie)
        Protocol.writePayloadLength(res, 2 + cookieLen)
        Protocol.writeInt2(res, cookieLen)
        Protocol.writeByteArray(res, self.cookie)
        return res

    @staticmethod
    def deserializeFrom(array: ByteView, length: int) -> "Optional[GameStatusRequest]":
        if length < 2:
            return None
        cookieLen = array.takeIntFromFirst(2)
        length -= 2
        if length != cookieLen:
            return None
        cookie = array.takeFirst(cookieLen)
        return GameStatusRequest(cookie)


class GameStatusResponse:
    def __init__(
        self,
        verdict: ProcessResponseError,
        hash: Optional[int] = None,
        status: Optional[Symbol] = None,
    ):
        self.verdict = verdict
        self.hash = hash
        self.status = status

    def serializeInto(self, res: bytearray) -> bytearray:
        Protocol.writePayloadLength(res, 2 + 8 + 1)
        Protocol.writeInt2(res, self.verdict)
        Protocol.writeInt8(res, self.hash if self.hash else 0)
        return Protocol.writeInt1(res, self.status if self.status else 0)

    @staticmethod
    def deserializeFrom(array: ByteView, _: int) -> "GameStatusResponse":
        verdict = ProcessResponseError(array.takeIntFromFirst(2))
        if int(verdict) != 0:
            array.takeFirst(8 + 1)
            return GameStatusResponse(verdict)
        hash = array.takeIntFromFirst(8)
        status = Symbol(array.takeIntFromFirst(1))
        return GameStatusResponse(verdict, hash, status)


class LoadBoardRequest:
    def __init__(self, cookie: Cookie):
        self.requestType = Requests.LoadBoard
        self.cookie = cookie

    def serializeInto(self, res: bytearray) -> bytearray:
        cookieLen = len(self.cookie)
        Protocol.writePayloadLength(res, 2 + cookieLen)
        Protocol.writeInt2(res, cookieLen)
        Protocol.writeByteArray(res, self.cookie)
        return res

    @staticmethod
    def deserializeFrom(array: ByteView, length: int) -> "Optional[LoadBoardRequest]":
        if length < 2:
            return None
        cookieLen = array.takeIntFromFirst(2)
        length -= 2
        if length != cookieLen:
            return None
        cookie = array.takeFirst(cookieLen)
        return LoadBoardRequest(cookie)


class LoadBoardResponse:
    def __init__(
        self, verdict: ProcessResponseError, board: Optional[bytearray] = None
    ):
        self.verdict = verdict
        self.board = board

    def serializeInto(self, res: bytearray) -> bytearray:
        reprLen = len(self.board) if self.board else 0
        Protocol.writePayloadLength(res, 2 + reprLen)
        Protocol.writeInt2(res, self.verdict)
        if reprLen > 0:
            assert self.board
            Protocol.writeByteArray(res, self.board)
        return res

    @staticmethod
    def deserializeFrom(array: ByteView, length: int) -> "LoadBoardResponse":
        verdict = ProcessResponseError(array.takeIntFromFirst(2))
        if verdict is not ProcessResponseError.SUCCESS:
            array.takeFirst(length - 2)
            return LoadBoardResponse(verdict)
        board = array.takeFirst(length - 2)
        return LoadBoardResponse(verdict, board)


class Protocol:
    @staticmethod
    def writeServerResponseHeaderWithoutLength(
        res: bytearray,
        requestType: Requests,
        error: ServerResponseError,
    ):
        Protocol.writeInt2(res, requestType)
        Protocol.writeInt2(res, error)
        return res

    @staticmethod
    def writePayloadLength(res: bytearray, length: int) -> bytearray:
        return Protocol.writeInt8(res, length)

    @staticmethod
    async def readServerResponseHeader(
        reader: asyncio.StreamReader,
    ) -> Tuple[Requests, ServerResponseError, int]:
        buffer = await reader.read(2 + 2 + 8)
        view = ByteView(bytearray(buffer))
        return (
            Requests(view.takeIntFromFirst(2)),
            ServerResponseError(view.takeIntFromFirst(2)),
            view.takeIntFromFirst(8),
        )

    @staticmethod
    def writeClientRequestHeaderWithoutLength(
        res: bytearray,
        requestType: Requests,
    ):
        Protocol.writeInt2(res, requestType)
        return res

    @staticmethod
    async def readClientRequestHeader(
        reader: asyncio.StreamReader,
    ) -> Tuple[Requests, int]:
        buffer = await reader.read(2 + 8)
        view = ByteView(bytearray(buffer))
        return (
            Requests(view.takeIntFromFirst(2)),
            view.takeIntFromFirst(8),
        )

    @staticmethod
    def writeInt10(res: bytearray, x: Any) -> bytearray:
        res.extend(int(x).to_bytes(10, byteorder="big"))
        return res

    @staticmethod
    def writeInt8(res: bytearray, x: Any) -> bytearray:
        res.extend(int(x).to_bytes(8, byteorder="big"))
        return res

    @staticmethod
    def writeInt4(res: bytearray, x: Any) -> bytearray:
        res.extend(int(x).to_bytes(4, byteorder="big"))
        return res

    @staticmethod
    def writeInt2(res: bytearray, x: Any) -> bytearray:
        res.extend(int(x).to_bytes(2, byteorder="big"))
        return res

    @staticmethod
    def writeInt1(res: bytearray, x: Any) -> bytearray:
        res.extend(int(x).to_bytes(1, byteorder="big"))
        return res

    @staticmethod
    def writeByteArray(res: bytearray, x: bytearray) -> bytearray:
        res.extend(x)
        return res

    @staticmethod
    def getByteArrayForInt(x: int) -> bytearray:
        return bytearray(x.to_bytes((min(x.bit_length(), 1) + 7) // 8, byteorder="big"))

    @staticmethod
    def requestType(entity: Any) -> Requests:
        if isinstance(entity, InitializeConnectionResponse):
            return Requests.InitializeConnection
        if isinstance(entity, MakeGameResponse):
            return Requests.MakeGame
        if isinstance(entity, JoinGameResponse):
            return Requests.JoinGame
        if isinstance(entity, MakeMoveResponse):
            return Requests.MakeMove
        if isinstance(entity, GameStatusResponse):
            return Requests.GameStatus
        if isinstance(entity, LoadBoardResponse):
            return Requests.LoadBoard
        assert False and "Unsuported request"

    @staticmethod
    def serializeClientRequest(entity: Any) -> bytearray:
        res = bytearray()
        Protocol.writeClientRequestHeaderWithoutLength(res, entity.requestType)
        return entity.serializeInto(res)

    @staticmethod
    def deserializeClientRequest(
        buffer: bytearray, requestType: Requests, length: int
    ) -> Optional[Any]:
        view = ByteView(buffer)
        if requestType is Requests.InitializeConnection:
            return InitializeConnectionRequest.deserializeFrom(view, length)
        if requestType is Requests.MakeGame:
            return MakeGameRequest.deserializeFrom(view, length)
        if requestType is Requests.JoinGame:
            return JoinGameRequest.deserializeFrom(view, length)
        if requestType is Requests.MakeMove:
            return MakeMoveRequest.deserializeFrom(view, length)
        if requestType is Requests.GameStatus:
            return GameStatusRequest.deserializeFrom(view, length)
        if requestType is Requests.LoadBoard:
            return LoadBoardRequest.deserializeFrom(view, length)
        return None

    @staticmethod
    def serializeServerResponse(entity: Any) -> bytearray:
        res = bytearray()
        Protocol.writeServerResponseHeaderWithoutLength(
            res, Protocol.requestType(entity), ServerResponseError.SUCCESS
        )
        return entity.serializeInto(res)

    @staticmethod
    def serializeServerResponseError(
        requestType: Requests, error: ServerResponseError
    ) -> bytearray:
        res = bytearray()
        Protocol.writeServerResponseHeaderWithoutLength(res, requestType, error)
        return Protocol.writePayloadLength(res, 0)

    @staticmethod
    def deserializeServerResponse(
        buffer: bytearray, requestType: Requests, length: int
    ) -> Optional[Any]:
        view = ByteView(buffer)
        if requestType is Requests.InitializeConnection:
            return InitializeConnectionResponse.deserializeFrom(view, length)
        if requestType is Requests.MakeGame:
            return MakeGameResponse.deserializeFrom(view, length)
        if requestType is Requests.JoinGame:
            return JoinGameResponse.deserializeFrom(view, length)
        if requestType is Requests.MakeMove:
            return MakeMoveResponse.deserializeFrom(view, length)
        if requestType is Requests.GameStatus:
            return GameStatusResponse.deserializeFrom(view, length)
        if requestType is Requests.LoadBoard:
            return LoadBoardResponse.deserializeFrom(view, length)
        return None
