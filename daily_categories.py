from dataclasses import dataclass


@dataclass(frozen=True)
class DailyCategory:
    key: str
    label: str
    group: str
    colour: str
    icon: str
    active: bool = True


DAILY_CATEGORIES = (
    DailyCategory("walk", "Walk", "movement", "#78b68b", "walk"),
    DailyCategory("run", "Run", "movement", "#dc786f", "run"),
    DailyCategory("swim", "Swim", "movement", "#61a9c4", "swim"),
    DailyCategory("dance", "Dance", "movement", "#b77bc9", "dance"),
    DailyCategory("cycling", "Bike", "movement", "#d0a64f", "cycling"),
    DailyCategory("low_sugar", "Low Sugar", "food", "#8fb76f", "low-sugar"),
    DailyCategory("cooked", "Cooked", "food", "#cf865f", "cooked"),
)


def active_categories() -> tuple[DailyCategory, ...]:
    return tuple(category for category in DAILY_CATEGORIES if category.active)
