from dataclasses import dataclass, field
from pathlib import Path

SCANNER_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class DatasetProfile:
    name: str
    root: Path
    source: str
    attribution: str
    license: str
    ignored_categories: tuple[str, ...]
    limitations: tuple[str, ...]
    category_aliases: dict[str, str] = field(default_factory=dict)


TOP_DOWN = DatasetProfile(
    name="top-down",
    root=SCANNER_ROOT / "data/raw/ChessTopDown.v2-chess2.coco",
    source="https://universe.roboflow.com/chess-gftva/chess-top-down",
    attribution="Chess Top Down Dataset by chess, Roboflow Universe, 2022",
    license="CC BY 4.0",
    ignored_categories=("chess-pieces",),
    limitations=(
        "Export contains existing augmentations and 416x416 stretching.",
        "Sparse positions do not establish performance on full armies or unseen boards.",
    ),
)

CHESS_V2 = DatasetProfile(
    name="chess-v2",
    root=SCANNER_ROOT / "data/raw/ChessV2.v1i.coco",
    source="https://universe.roboflow.com/public-wspace/chess-v2-qqtmk",
    attribution="Chess V2 Dataset by Public Wspace, Roboflow Universe, 2022",
    license="CC BY 4.0",
    ignored_categories=("Chess",),
    limitations=(
        "Export README reports no augmentation; this does not prove upstream originals are unique.",
        "Crowded or artificial positions may contain more than 32 pieces or duplicate annotations.",
    ),
    category_aliases={
        "BB": "black-bishop",
        "BK": "black-king",
        "BKN": "black-knight",
        "BP": "black-pawn",
        "BQ": "black-queen",
        "BR": "black-rook",
        "WB": "white-bishop",
        "WK": "white-king",
        "WKN": "white-knight",
        "WP": "white-pawn",
        "WQ": "white-queen",
        "WR": "white-rook",
    },
)

DATASETS = {profile.name: profile for profile in (TOP_DOWN, CHESS_V2)}


def prepared_directory(profile: DatasetProfile) -> Path:
    artifacts = SCANNER_ROOT / "artifacts"
    return (
        artifacts / "prepared"
        if profile.name == "top-down"
        else artifacts / profile.name / "prepared"
    )
