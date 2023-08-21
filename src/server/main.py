import argparse
import sys

from pathlib import Path

sys.path[0] = str(Path(__file__).absolute().parent.parent)

from server.process import ServerController, ServerProcess


def main():
    argParser = argparse.ArgumentParser()
    argParser.add_argument("-port", required=True)
    args = argParser.parse_args()

    process = ServerProcess()
    controller = ServerController(process, '127.0.0.1', args.port)
    controller.runServer()


if __name__ == "__main__":
    main()
