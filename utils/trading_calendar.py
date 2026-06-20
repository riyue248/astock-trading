"""
A股交易时段判断
"""
from datetime import datetime, date, time
from zoneinfo import ZoneInfo

from config import settings

CN_TZ = ZoneInfo("Asia/Shanghai")

# 2026年节假日
HOLIDAYS_2026: set[date] = {
    date(2026,1,1), date(2026,1,2), date(2026,1,3),
    date(2026,1,17), date(2026,1,18), date(2026,1,19),
    date(2026,1,20), date(2026,1,21), date(2026,1,22), date(2026,1,23),
    date(2026,4,4), date(2026,4,5), date(2026,4,6),
    date(2026,5,1), date(2026,5,2), date(2026,5,3), date(2026,5,4), date(2026,5,5),
    date(2026,6,19), date(2026,6,20), date(2026,6,21),
    date(2026,9,24), date(2026,9,25), date(2026,9,26),
    date(2026,10,1), date(2026,10,2), date(2026,10,3),
    date(2026,10,4), date(2026,10,5), date(2026,10,6), date(2026,10,7),
}


def is_holiday(d: date) -> bool:
    if d in HOLIDAYS_2026:
        return True
    return d.weekday() >= 5


def is_trading_time(dt: datetime = None) -> tuple[bool, str]:
    if dt is None:
        dt = datetime.now(CN_TZ)
    today = dt.date()
    current_time = dt.time()

    if is_holiday(today):
        return False, "holiday"
    if settings.MORNING_START <= current_time < settings.MORNING_END:
        return True, "live"
    if settings.MORNING_END <= current_time < settings.AFTERNOON_START:
        return False, "lunch_break"
    if settings.AFTERNOON_START <= current_time < settings.AFTERNOON_END:
        return True, "live"
    return False, "closed"
