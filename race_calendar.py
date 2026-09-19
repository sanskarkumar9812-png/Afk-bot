"""
Official 2026 Formula 1 World Championship calendar.

Source: formula1.com/en/racing/2026 (fetched September 2026). Race weekends
are Friday-Sunday unless noted; `race_date` is the Sunday race day, used to
decide when a prediction round should open, lock, and be auto-scored.

THIS WILL GO STALE FOR 2027+. Update CALENDAR below each off-season —
that's the only place season dates live.
"""

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass
class RaceWeekend:
    round: int
    name: str          # display name, e.g. "Spanish Grand Prix"
    location: str
    race_date: date    # the Sunday (race day)

    @property
    def weekend_start(self) -> date:
        return self.race_date - timedelta(days=2)


CALENDAR = [
    RaceWeekend(1, "Australian Grand Prix", "Melbourne", date(2026, 3, 8)),
    RaceWeekend(2, "Chinese Grand Prix", "Shanghai", date(2026, 3, 15)),
    RaceWeekend(3, "Japanese Grand Prix", "Suzuka", date(2026, 3, 29)),
    RaceWeekend(4, "Miami Grand Prix", "Miami", date(2026, 5, 3)),
    RaceWeekend(5, "Canadian Grand Prix", "Montreal", date(2026, 5, 24)),
    RaceWeekend(6, "Monaco Grand Prix", "Monte Carlo", date(2026, 6, 7)),
    RaceWeekend(7, "Gran Premio de Barcelona-Catalunya", "Barcelona", date(2026, 6, 14)),
    RaceWeekend(8, "Austrian Grand Prix", "Spielberg", date(2026, 6, 28)),
    RaceWeekend(9, "British Grand Prix", "Silverstone", date(2026, 7, 5)),
    RaceWeekend(10, "Belgian Grand Prix", "Spa-Francorchamps", date(2026, 7, 19)),
    RaceWeekend(11, "Hungarian Grand Prix", "Budapest", date(2026, 7, 26)),
    RaceWeekend(12, "Dutch Grand Prix", "Zandvoort", date(2026, 8, 23)),
    RaceWeekend(13, "Italian Grand Prix", "Monza", date(2026, 9, 6)),
    RaceWeekend(14, "Spanish Grand Prix", "Madrid (MADRING)", date(2026, 9, 13)),
    RaceWeekend(15, "Azerbaijan Grand Prix", "Baku", date(2026, 9, 26)),
    RaceWeekend(16, "Bahrain Grand Prix", "Malaysia", date(2026, 10, 4)),
    RaceWeekend(17, "Singapore Grand Prix", "Singapore", date(2026, 10, 11)),
    RaceWeekend(18, "United States Grand Prix", "Austin", date(2026, 10, 25)),
    RaceWeekend(19, "Mexico City Grand Prix", "Mexico City", date(2026, 11, 1)),
    RaceWeekend(20, "São Paulo Grand Prix", "Sao Paulo", date(2026, 11, 8)),
    RaceWeekend(21, "Las Vegas Grand Prix", "Las Vegas", date(2026, 11, 21)),
    RaceWeekend(22, "Qatar Grand Prix", "Lusail", date(2026, 11, 29)),
    RaceWeekend(23, "Abu Dhabi Grand Prix", "Yas Marina", date(2026, 12, 6)),
]


def get_next_race(today: date = None) -> RaceWeekend:
    """Returns the next race weekend. If `today` falls inside a race weekend
    (Fri-Sun), that weekend is returned rather than the one after it, so a
    chat mid-race-weekend still sees the correct GP for predictions."""
    today = today or date.today()
    for race in CALENDAR:
        if today <= race.race_date:
            return race
    return None  # season is over


def get_race_by_name(name: str):
    for race in CALENDAR:
        if race.name.lower() == name.lower():
            return race
    return None


def days_until(race: RaceWeekend, today: date = None) -> int:
    today = today or date.today()
    return (race.race_date - today).days
