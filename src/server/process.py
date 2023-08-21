import asyncio
import secrets
import time

from typing import Optional, Set, Dict

from server.model import ServerGame
from model import *

"""
requests:
1. create new game from scratch        +
2. create new game from stored data 
3. save game data
4. get cookie                          +
5. join game by id                     +
6. get full board in game              +
7. get next move in game               ?
8. make move in game                   +
"""

PlayerId = int
Timepoint = float


class ServerProcess:
    gameLimit = 10
    clientLimit = 1000
    maxCookies = 10000
    cookieTimeout = 600
    cookieBytes = 128
    gameIdDigits = 20

    def __init__(self):
        # Owns ServerGame
        self.games: Dict[GameId, ServerGame] = {}
        # Owns Player
        self.players: Dict[PlayerId, Player] = {}
        self.nextPlayerId = 1
        # Refers to Player
        self.cookieToPlayer: Dict[Cookie, Player] = {}
        self.cookies: Dict[Cookie, Timepoint] = {}

    def generateGameId(self) -> GameId:
        gameId: Optional[GameId] = None
        while gameId is None or gameId in self.games:
            gameId = secrets.choice(range(
                10**ServerProcess.gameIdDigits,
                10 ** (ServerProcess.gameIdDigits + 1) - 1,
            ))
        return gameId

    def cleanupOldCookies(self):
        now = time.time()
        toDelete: Set[bytearray] = set()
        for cookie, actuality in self.cookies.items():
            if actuality - now > ServerProcess.cookieTimeout:
                toDelete.add(cookie)
        for cookie in toDelete:
            del self.cookies[cookie]
        # TODO: delete game which is not played anymore

    def initializeConnection(self, name: str) -> InitializeConnectionResponse:
        if len(self.cookies) >= ServerProcess.maxCookies:
            return InitializeConnectionResponse(ProcessResponseError.OVERLOADED)
        cookie: Optional[bytearray] = None
        while cookie is None or cookie in self.cookies:
            cookie = bytearray(secrets.token_bytes(ServerProcess.cookieBytes))
        self.cookies[cookie] = time.time()
        newPlayer = Player(self.nextPlayerId, name)
        self.players[self.nextPlayerId] = newPlayer
        self.cookieToPlayer[cookie] = newPlayer
        self.nextPlayerId += 1
        return InitializeConnectionResponse(ProcessResponseError.SUCCESS, cookie)

    def makeGame(self, initRadius: int) -> MakeGameResponse:
        if len(self.games) > ServerProcess.gameLimit:
            return MakeGameResponse(ProcessResponseError.OVERLOADED)
        gameId = self.generateGameId()
        self.games[gameId] = ServerGame([], initRadius)
        return MakeGameResponse(ProcessResponseError.SUCCESS, gameId)

    def joinGame(
        self, cookie: Cookie, gameId: GameId, symbol: Symbol
    ) -> JoinGameResponse:
        if cookie not in self.cookieToPlayer:
            return JoinGameResponse(ProcessResponseError.COOKIE_NOT_FOUND)
        if gameId not in self.games:
            return JoinGameResponse(ProcessResponseError.GAME_NOT_FOUND)
        player = self.cookieToPlayer[cookie]
        player.gameId = gameId
        game = self.games[gameId]

        symbols = list(
            filter(
                lambda x: x is not Symbol.BLANK, [player.sym for player in game.players]
            )
        )
        if symbol is not Symbol.BLANK and symbols:
            return JoinGameResponse(ProcessResponseError.ALREADY_IN_USE)
        if symbol is Symbol.BLANK:
            if symbols:
                chosenSymbol = invertTeam(symbols[0])
            else:
                chosenSymbol = secrets.choice([Symbol.CROSS, Symbol.NOUGHT])
        else:
            chosenSymbol = symbol
        player.sym = chosenSymbol
        game.players.append(player)
        boardRepr = bytearray()
        game.board.dumpByteRepr(boardRepr)
        return JoinGameResponse(ProcessResponseError.SUCCESS, boardRepr, chosenSymbol)

    def makeMove(self, cookie: Cookie, position: Position) -> MakeMoveResponse:
        if cookie not in self.cookieToPlayer:
            return MakeMoveResponse(ProcessResponseError.COOKIE_NOT_FOUND)
        player = self.cookieToPlayer[cookie]
        if player.gameId < 0:
            return MakeMoveResponse(ProcessResponseError.PLAYER_NOT_IN_GAME)
        if player.gameId not in self.games:
            return MakeMoveResponse(ProcessResponseError.GAME_NOT_FOUND)
        game = self.games[player.gameId]
        res = game.makeMove(position, player.sym)
        if res is MoveError.SUCCESS:
            return MakeMoveResponse(
                ProcessResponseError.SUCCESS, game.board.hash(), game.status
            )
        return MakeMoveResponse(res)

    def gameStatus(self, cookie: Cookie) -> GameStatusResponse:
        if cookie not in self.cookieToPlayer:
            return GameStatusResponse(ProcessResponseError.COOKIE_NOT_FOUND)
        player = self.cookieToPlayer[cookie]
        if player.gameId < 0:
            return GameStatusResponse(ProcessResponseError.PLAYER_NOT_IN_GAME)
        if player.gameId not in self.games:
            return GameStatusResponse(ProcessResponseError.GAME_NOT_FOUND)
        game = self.games[player.gameId]
        return GameStatusResponse(
            ProcessResponseError.SUCCESS, game.board.hash(), game.status
        )

    def loadBoard(self, cookie: Cookie) -> LoadBoardResponse:
        if cookie not in self.cookieToPlayer:
            return LoadBoardResponse(ProcessResponseError.COOKIE_NOT_FOUND)
        player = self.cookieToPlayer[cookie]
        if player.gameId < 0:
            return LoadBoardResponse(ProcessResponseError.PLAYER_NOT_IN_GAME)
        if player.gameId not in self.games:
            return LoadBoardResponse(ProcessResponseError.GAME_NOT_FOUND)
        game = self.games[player.gameId]
        boardRepr = bytearray()
        game.board.dumpByteRepr(boardRepr)
        return LoadBoardResponse(ProcessResponseError.SUCCESS, boardRepr)


class ServerController:
    def __init__(self, process: ServerProcess, host: str, port: int):
        self.process = process
        self.host = host
        self.port = port

    async def serve(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        requestType, length = await Protocol.readClientRequestHeader(reader)
        buffer = await reader.read(length)
        view = ByteView(bytearray(buffer))
        response = None
        if requestType is Requests.InitializeConnection:
            request = InitializeConnectionRequest.deserializeFrom(view, length)
            if request is not None:
                response = Protocol.serializeServerResponse(
                    self.process.initializeConnection(request.name)
                )
        elif requestType is Requests.MakeGame:
            request = MakeGameRequest.deserializeFrom(view, length)
            if request is not None:
                response = Protocol.serializeServerResponse(
                    self.process.makeGame(request.initRadius)
                )
        elif requestType is Requests.JoinGame:
            request = JoinGameRequest.deserializeFrom(view, length)
            if request is not None:
                response = Protocol.serializeServerResponse(
                    self.process.joinGame(
                        request.cookie, request.gameId, request.symbol
                    )
                )
        elif requestType is Requests.MakeMove:
            request = MakeMoveRequest.deserializeFrom(view, length)
            if request is not None:
                response = Protocol.serializeServerResponse(
                    self.process.makeMove(request.cookie, request.position)
                )
        elif requestType is Requests.GameStatus:
            request = GameStatusRequest.deserializeFrom(view, length)
            if request is not None:
                response = Protocol.serializeServerResponse(
                    self.process.gameStatus(request.cookie)
                )
        elif requestType is Requests.LoadBoard:
            request = LoadBoardRequest.deserializeFrom(view, length)
            if request is not None:
                response = Protocol.serializeServerResponse(
                    self.process.loadBoard(request.cookie)
                )

        if response is None:
            response = Protocol.serializeServerResponseError(
                requestType, ServerResponseError.BAD_REQUEST
            )
        writer.write(response)
        await writer.drain()
        writer.close()

    def runServer(self):
        async def runServer(self: ServerController):
            server = await asyncio.start_server(self.serve, self.host, self.port)
            await server.serve_forever()
        asyncio.run(runServer(self))
