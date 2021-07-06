import re
import logging
from typing import cast, Union, Optional, Match
from datetime import datetime, date, timedelta, timezone

from prefixdate.precision import Precision

log = logging.getLogger(__name__)

Raw = Union[None, str, date, datetime, int, "DatePrefix"]

REGEX = re.compile(
    r"^((?P<year>[12]\d{3})"
    r"(-(?P<month>[01]?[0-9])"
    r"(-(?P<day>[0123]?[0-9])"
    r"([T ]"
    r"((?P<hour>[012]?\d)"
    r"(:(?P<minute>\d{1,2})"
    r"(:(?P<second>\d{1,2})"
    r"(\.\d{6})?"
    r"(Z|(?P<tzsign>[-+])(?P<tzhour>\d{2})(:?(?P<tzminute>\d{2}))"
    r"?)?)?)?)?)?)?)?)?.*"
)


class DatePrefix(object):
    """A date that is specified in terms of a value and an additional precision,
    which defines how well specified the date is. A datetime representation is
    provided, but it is not aware of the precision aspect."""

    __slots__ = ["precision", "dt", "text"]

    def __init__(self, raw: Raw, precision: Precision = Precision.FULL):
        self.precision = precision
        self.dt: Optional[datetime] = self._parse(raw)
        self.text: Optional[str] = None
        if self.dt is not None and self.precision != Precision.EMPTY:
            utc_dt = self.dt.astimezone(timezone.utc)
            self.text = utc_dt.isoformat()[: self.precision.value]

    def _parse(self, raw: Raw) -> Optional[datetime]:
        try:
            match = cast(Match[str], REGEX.match(raw))  # type: ignore
        except TypeError:
            if isinstance(raw, datetime):
                return raw
            if isinstance(raw, date):
                return self._parse(raw.isoformat())
            if isinstance(raw, int):
                if 1000 < raw < 9999:
                    return self._parse(str(raw))
            if isinstance(raw, DatePrefix):
                self.precision = raw.precision
                return raw.dt
            log.warning("Date value is invalid: %s", raw)
            return None
        year = self._extract(match, "year", Precision.EMPTY)
        month = self._extract(match, "month", Precision.YEAR)
        day = self._extract(match, "day", Precision.MONTH)
        hour = self._extract(match, "hour", Precision.DAY)
        minute = self._extract(match, "minute", Precision.HOUR)
        second = self._extract(match, "second", Precision.DAY)
        try:
            return datetime(
                year or 1000,
                month or 1,
                day or 1,
                hour or 0,
                minute or 0,
                second or 0,
                tzinfo=self._tzinfo(match),
            )
        except ValueError:
            log.warning("Date string is invalid: %s", raw)
            return None

    def _extract(
        self, match: Match[str], group: str, precision: Precision
    ) -> Optional[int]:
        try:
            value = int(match.group(group))
            if value > 0:
                return value
        except (ValueError, TypeError, AttributeError):
            pass
        pval = min(self.precision.value, precision.value)
        self.precision = Precision(pval)
        return None

    def _tzinfo(self, match: Match[str]) -> timezone:
        """Parse the time zone information from a datetime string."""
        # This is probably a bit rough-and-ready, there are good libraries
        # for this. Do we want to depend on one of them?
        try:
            sign = -1 if match.group("tzsign") == "-" else 1
            hours = sign * int(match.group("tzhour"))
            minutes = sign * int(match.group("tzminute"))
            delta = timedelta(hours=hours, minutes=minutes)
            return timezone(delta)
        except (ValueError, TypeError, AttributeError):
            pass
        return timezone.utc

    def __eq__(self, other: object) -> bool:
        return str(self) == str(other)

    def __str__(self) -> str:
        return self.text or ""

    def __repr__(self) -> str:
        return "<DatePrefix(%r, %r)>" % (self.text, self.precision)
