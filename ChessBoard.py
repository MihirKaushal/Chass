# Mihir Kaushal

import ChessPieces

# make ChessBoardSquare class, stores the color of square and the piece that is on it
class ChessBoardSquare:
    # constructor 
    def __init__(self, isWhite, piece):
        self.isWhite = isWhite
        self.piece = piece

    # print format
    def __repr__(self):
        if (self.piece == None) and (self.isWhite):
            return "\u25FB"
        elif(self.piece == None):
            return "\u25FC"
        else: 
            return str(self.piece)


# ChessBoard class
class ChessBoard:
    # constructor makes an empty board
    def __init__(self):
        # fills up empty 8x8 matrix with ChessBoardSquare objects, in check pattern
        self.board = [[None] * 8 for column in range(8)]
        for row in range(len(self.board)):
            for column in range(len(self.board[row])):
                if ((row + column) % 2 == 0):
                    self.board[row][column] = ChessBoardSquare(True, None)
                else:
                    self.board[row][column] = ChessBoardSquare(False, None)
        print("Empty chess board (dark mode on VSCode will make the colors inversed):")
        self.printBoard()
        self.setBoard()

    # sets the borad up according to chess rules
    def setBoard(self):
        # first, fills the top row with the appropriate black pieces
        self.board[0][0] = ChessBoardSquare(True, ChessPieces.Rook(False))
        self.board[0][1] = ChessBoardSquare(False, ChessPieces.Knight(False))
        self.board[0][2] = ChessBoardSquare(True, ChessPieces.Bishop(False))
        self.board[0][3] = ChessBoardSquare(False, ChessPieces.Queen(False))
        self.board[0][4] = ChessBoardSquare(True, ChessPieces.King(False))
        self.board[0][5] = ChessBoardSquare(False, ChessPieces.Bishop(False))
        self.board[0][6] = ChessBoardSquare(True, ChessPieces.Knight(False))
        self.board[0][7] = ChessBoardSquare(False, ChessPieces.Rook(False))

        # second, fills up the second row with black pawns
        for column in range(len(self.board[1])):
            if (column % 2 == 0):
                self.board[1][column] = ChessBoardSquare(False, ChessPieces.Pawn(False))
            else:
                self.board[1][column] = ChessBoardSquare(True, ChessPieces.Pawn(False))
        
        # third, fills up second row from bottom with white pawns
        for column in range(len(self.board[6])):
            if (column % 2 == 0):
                self.board[6][column] = ChessBoardSquare(True, ChessPieces.Pawn(True))
            else:
                self.board[6][column] = ChessBoardSquare(False, ChessPieces.Pawn(True))

        # forth, fills up bottom row with the appropriate white pieces
        self.board[7][0] = ChessBoardSquare(False, ChessPieces.Rook(True))
        self.board[7][1] = ChessBoardSquare(True, ChessPieces.Knight(True))
        self.board[7][2] = ChessBoardSquare(False, ChessPieces.Bishop(True))
        self.board[7][3] = ChessBoardSquare(True, ChessPieces.Queen(True))
        self.board[7][4] = ChessBoardSquare(False, ChessPieces.King(True))
        self.board[7][5] = ChessBoardSquare(True, ChessPieces.Bishop(True))
        self.board[7][6] = ChessBoardSquare(False, ChessPieces.Knight(True))
        self.board[7][7] = ChessBoardSquare(True, ChessPieces.Rook(True))

        # print board after setup
        print("Chess board after setup (dark mode on VSCode will make the colors inversed):")
        self.printBoard()

    # moves a piece 
    def move(self, fromRow, fromColumn, toRow, toColumn):
        # store piece og square
        tempPiece = self.board[fromRow][fromColumn].piece
        # store piece on new square
        capturedPiece = self.board[toRow][toColumn].piece

        # get fromColumnID
        if (fromColumn == 0):
            fromColumnID = "a"
        elif (fromColumn == 1):
            fromColumnID = "b"
        elif (fromColumn == 2):
            fromColumnID = "c"
        elif (fromColumn == 3):
            fromColumnID = "d"
        elif (fromColumn == 4):
            fromColumnID = "e"
        elif (fromColumn == 5):
            fromColumnID = "f"
        elif (fromColumn == 6):
            fromColumnID = "g"
        elif (fromColumn == 7):
            fromColumnID = "h"

        # get toColumnID
        if (toColumn == 0):
            toColumnID = "a"
        elif (toColumn == 1):
            toColumnID = "b"
        elif (toColumn == 2):
            toColumnID = "c"
        elif (toColumn == 3):
            toColumnID = "d"
        elif (toColumn == 4):
            toColumnID = "e"
        elif (toColumn == 5):
            toColumnID = "f"
        elif (fromRow == 6):
            toColumnID = "g"
        elif (toColumn == 7):
            toColumnID = "h"

        # remove piece from previous position
        if ((fromRow + fromColumn) % 2 == 0):
            self.board[fromRow][fromColumn] = ChessBoardSquare(True, None)
        else:
            self.board[fromRow][fromColumn] = ChessBoardSquare(False, None)

        # add piece to new position
        if ((toRow + toColumn) % 2 == 0):
            self.board[toRow][toColumn] = ChessBoardSquare(True, tempPiece)
        else:
            self.board[toRow][toColumn] = ChessBoardSquare(False, tempPiece)

        # print board after every move
        if (capturedPiece != None):
            print(tempPiece.getName(), " moved from ", fromColumnID, (8 - fromRow), " to ", toColumnID, (8 - toRow), ", captured ", capturedPiece.getName(), sep = "")
        else:
            print(tempPiece.getName(), " moved from ", fromColumnID, (8 - fromRow), " to ", toColumnID, (8 - toRow), ", captured nothing", sep = "")
        print("(dark mode on VSCode will make the colors inversed):")
        self.printBoard()

    # prints the chess board
    def printBoard(self):
        for row in self.board:
            print(row)
        print()
        print()

