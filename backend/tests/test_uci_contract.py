import asyncio

import pytest

from backend.analysis.fairy import FairyStockfishUciProvider
from backend.analysis.stockfish import StockfishUciProvider, parse_uci_info


@pytest.mark.parametrize(
    "line",
    [
        "info score cp nope",
        "info score mate",
        "info score unknown 5",
        "info wdl 100 200",
        "info wdl -1 1001 0",
        "info wdl 1 1 1",
        "info depth -1",
        "info nodes nope",
        "info multipv 0",
    ],
)
def test_rejects_malformed_numeric_uci(line):
    with pytest.raises(ValueError):
        parse_uci_info(line)


def test_uci_free_text_is_not_parsed_as_score_data():
    assert parse_uci_info("info string NNUE score cache nodes unknown") == {}


def scripted_provider(lines):
    provider = StockfishUciProvider(configured_path="unused")
    iterator = iter(lines)

    async def read():
        return next(iterator)

    async def noop(*args, **kwargs):
        pass

    provider._readline = read
    provider._write = noop
    provider._set_search_options_locked = noop
    return provider


def test_latest_score_does_not_reuse_stale_wdl():
    provider = scripted_provider(
        [
            "info depth 1 score cp 20 wdl 300 400 300",
            "info depth 2 score cp 100",
            "bestmove e2e4",
        ]
    )
    result = asyncio.run(provider._search_locked("test"))
    assert result.centipawns == 100 and result.win is None


def test_bound_scores_do_not_replace_exact_evaluations():
    provider = scripted_provider(
        [
            "info depth 1 score cp 20",
            "info depth 2 score cp 100 lowerbound",
            "bestmove e2e4",
        ]
    )
    assert asyncio.run(provider._search_locked("test")).centipawns == 20


def test_analysis_rejects_missing_evaluation_and_incomplete_bestmove():
    for lines, error in [
        (["info depth 1 nodes 10", "bestmove e2e4"], RuntimeError),
        (["info score cp 20", "bestmove"], ValueError),
    ]:
        with pytest.raises(error):
            asyncio.run(scripted_provider(lines)._search_locked("test"))


def test_fairy_terminal_probe_does_not_reuse_a_stale_mate():
    provider = scripted_provider(["info score mate 1", "info score cp 0", "bestmove (none)"])
    assert (
        asyncio.run(FairyStockfishUciProvider._terminal_outcome_locked(provider, "test", "white"))
        == "draw"
    )


def test_fairy_terminal_probe_requires_draw_evidence():
    provider = scripted_provider(["info depth 1", "bestmove (none)"])
    with pytest.raises(ValueError):
        asyncio.run(FairyStockfishUciProvider._terminal_outcome_locked(provider, "test", "white"))


@pytest.mark.parametrize("last_line", ["bestmove", "bestmove (none)", "bestmove e7e5"])
def test_bot_search_requires_actual_authorized_bestmove(last_line):
    provider = scripted_provider(["info depth 1 score cp 20 pv e2e4", last_line])
    with pytest.raises(ValueError):
        asyncio.run(
            provider._search_moves_locked(
                "test",
                search_moves=["e2e4"],
                multipv=1,
                nodes=None,
                movetime_ms=25,
                limit_strength_elo=None,
            )
        )
