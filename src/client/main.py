import argparse
import os
import sys

sys.path.insert(1, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    argParser = argparse.ArgumentParser()
    args = argParser.parse_args()


if __name__ == "__main__":
    main()
