import json

from ChessBoard import ChessBoard


def main() -> None:
    board = ChessBoard(size=8)
    move = board.move(6, 4, 4, 4)

    payload = {
        "move": move,
        "state": board.to_json(),
    }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
