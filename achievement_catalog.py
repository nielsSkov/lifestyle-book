from collections.abc import Collection
from dataclasses import dataclass


@dataclass(frozen=True)
class Achievement:
    key: str
    label: str
    group: str
    colour: str
    selected_colour: str
    tile_colour: str
    icon: str
    active: bool = True


ACHIEVEMENTS = (
    Achievement("walk", "Walk", "movement", "#78b68b", "#3b5745", "#3f8659", "walk"),
    Achievement("run", "Run", "movement", "#dc786f", "#68413f", "#a94f4a", "run"),
    Achievement("swim", "Swim", "movement", "#61a9c4", "#34505d", "#377992", "swim"),
    Achievement("dance", "Dance", "movement", "#b77bc9", "#563d60", "#7e4695", "dance"),
    Achievement("bike", "Bike", "movement", "#d0a64f", "#62522d", "#927126", "bike"),
    Achievement("yoga", "Yoga", "movement", "#9b8bd1", "#4a4268", "#6f5ca5", "yoga"),
    Achievement(
        "roller_skate",
        "Roller Skate",
        "movement",
        "#67b4a5",
        "#345a52",
        "#3b8176",
        "roller-skate",
        active=False,
    ),
    Achievement(
        "other_activity",
        "Other Activity",
        "movement",
        "#9b86cb",
        "#4c4064",
        "#7054a3",
        "other-activity",
    ),
    Achievement(
        "low_sugar",
        "Low Sugar",
        "food",
        "#8fb76f",
        "#465a35",
        "#5d8339",
        "low-sugar",
    ),
    Achievement("cooked", "Cooked", "food", "#cf865f", "#604137", "#98513a", "cooked"),
)


def configured_achievements(
    selected_keys: Collection[str] | None = None,
) -> tuple[Achievement, ...]:
    if selected_keys is None:
        return tuple(achievement for achievement in ACHIEVEMENTS if achievement.active)

    selected = set(selected_keys)
    known = {achievement.key for achievement in ACHIEVEMENTS}
    if selected - known:
        raise ValueError("Unknown achievement selected")
    return tuple(achievement for achievement in ACHIEVEMENTS if achievement.key in selected)
