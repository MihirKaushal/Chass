"""Launch the configured binaries and verify real UCI results, not mocked availability."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.analysis.classic import classic_position_fen  # noqa: E402
from backend.analysis.fairy import FairyStockfishUciProvider  # noqa: E402
from backend.analysis.profiles import analysis_position_fen, select_analysis_profile  # noqa: E402
from backend.analysis.stockfish import StockfishUciProvider  # noqa: E402
from backend.config import get_settings  # noqa: E402
from backend.rules import RuleEngine  # noqa: E402
from scripts.verification_positions import starting_state  # noqa: E402


def uci_moves(state, engine):
    return [
        f"{chr(97 + m.from_col)}{state.board.rows - m.from_row}{chr(97 + m.to_col)}{state.board.rows - m.to_row}"
        for m in engine.get_valid_moves_for_current_player(state)
    ]


async def smoke():
    settings, engine = get_settings(), RuleEngine()
    stockfish = StockfishUciProvider(configured_path=settings.stockfish_path, movetime_ms=60)
    fairy = FairyStockfishUciProvider(configured_path=settings.fairy_stockfish_path, movetime_ms=60)
    try:
        state = starting_state()
        fen = classic_position_fen(state)
        analysis = await stockfish.analyze(fen)
        legal = uci_moves(state, engine)
        move = await stockfish.search_moves(fen, search_moves=legal, movetime_ms=60)
        assert move.best_move in legal and (
            analysis.centipawns is not None or analysis.mate_in is not None
        )
        variant = starting_state(10, 10)
        profile = select_analysis_profile(variant).profile
        assert profile and profile.engine_id == "fairy-stockfish"
        fen = analysis_position_fen(variant, profile)
        inspection = await fairy.inspect_position(
            fen, profile, rows=10, cols=10, side_to_move="white"
        )
        expected = frozenset(
            (m.from_row, m.from_col, m.to_row, m.to_col)
            for m in engine.get_valid_moves_for_current_player(variant)
        )
        assert inspection.legal_moves == expected
        variant_analysis = await fairy.analyze(fen, profile)
        legal = uci_moves(variant, engine)
        reply = await fairy.search_moves(fen, profile, search_moves=legal, movetime_ms=60)
        assert reply.best_move in legal and (
            variant_analysis.centipawns is not None or variant_analysis.mate_in is not None
        )
        terminal_checks = []
        for queen_col, expected_status, expected_winner in [
            (9, "checkmate", "white"),
            (7, "stalemate", "draw"),
        ]:
            terminal = variant.clone()
            pieces = {
                (p.color, p.type): p.model_copy(deep=True)
                for row in variant.board.grid
                for p in row
                if p and p.type in {"king", "queen"}
            }
            terminal.board.grid = [[None] * 10 for _ in range(10)]
            terminal.board.grid[0][9] = pieces[("black", "king")]
            terminal.board.grid[2][8] = pieces[("white", "king")]
            terminal.board.grid[1][queen_col] = pieces[("white", "queen")]
            for row in terminal.board.grid:
                for piece in row:
                    if piece:
                        piece.has_moved = True
            terminal.current_player = "black"
            engine.evaluate_state(terminal)
            assert terminal.game_status == expected_status
            result = await fairy.inspect_position(
                analysis_position_fen(terminal, profile),
                profile,
                rows=10,
                cols=10,
                side_to_move="black",
                probe_terminal=True,
            )
            assert not result.legal_moves and result.terminal_outcome == expected_winner
            terminal_checks.append(expected_status)
        return {
            "stockfish": {"version": analysis.engine_version, "legalMove": move.best_move},
            "fairy": {
                "version": variant_analysis.engine_version,
                "legalMove": reply.best_move,
                "parityMoves": len(expected),
                "terminalChecks": terminal_checks,
            },
            "status": "passed",
        }
    finally:
        await stockfish.close()
        await fairy.close()


if __name__ == "__main__":
    print(json.dumps(asyncio.run(asyncio.wait_for(smoke(), timeout=60)), indent=2))
