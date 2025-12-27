# Mihir Kaushal

# parent class for all chess pieces
class ChessPiece:
    def __init__(self, isWhite, points):
        self.isWhite = isWhite
        self.points = points

class Pawn(ChessPiece):
    def __init__(self, isWhite):
        super().__init__(isWhite, 1)

    def __repr__(self):
        if self.isWhite:
            return "\u2659"
        else:
            return "\u265F"
        
    def getName(self):
        if (self.isWhite):
            return "White Pawn"
        else:
            return "Black Pawn"
        
class King(ChessPiece):
    def __init__(self, isWhite):
        super().__init__(isWhite, 67)

    def __repr__(self):
        if self.isWhite:
            return "\u2654"
        else:
            return "\u265A"
        
    def getName(self):
        if (self.isWhite):
            return "White King"
        else:
            return "Black King"
        
class Queen(ChessPiece):
    def __init__(self, isWhite):
        super().__init__(isWhite, 9)

    def __repr__(self):
        if self.isWhite:
            return "\u2655"
        else:
            return "\u265B"
        
    def getName(self):
        if (self.isWhite):
            return "White Queen"
        else:
            return "Black Queen"

class Rook(ChessPiece):
    def __init__(self, isWhite):
        super().__init__(isWhite, 5)

    def __repr__(self):
        if self.isWhite:
            return "\u2656"
        else:
            return "\u265C"
        
    def getName(self):
        if (self.isWhite):
            return "White Rook"
        else:
            return "Black Rook"

class Bishop(ChessPiece):
    def __init__(self, isWhite):
        super().__init__(isWhite, 3)

    def __repr__(self):
        if self.isWhite:
            return "\u2657"
        else:
            return "\u265D"
        
    def getName(self):
        if (self.isWhite):
            return "White Bishop"
        else:
            return "Black Bishop"

class Knight(ChessPiece):
    def __init__(self, isWhite):
        super().__init__(isWhite, 3)

    def __repr__(self):
        if self.isWhite:
            return "\u2658"
        else:
            return "\u265E"
        
    def getName(self):
        if (self.isWhite):
            return "White Knight"
        else:
            return "Black Knight"

