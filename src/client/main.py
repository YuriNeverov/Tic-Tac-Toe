import argparse
import sys

from pathlib import Path

sys.path.insert(1, Path(__file__).absolute().parent.parent.as_posix())


def main():
    argParser = argparse.ArgumentParser()
    args = argParser.parse_args()


if __name__ == "__main__":
    main()
