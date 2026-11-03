#!/usr/bin/env python3
"""Choose independent API Market Scan dates in Europe/Warsaw."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import argparse

def scan_dates(today: date, horizon: int = 3):
    if not 1 <= horizon <= 7:
        raise ValueError("horizon must be between 1 and 7")
    return [(today + timedelta(days=i)).isoformat() for i in range(horizon)]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", help="YYYY-MM-DD; defaults to Warsaw today")
    parser.add_argument("--days", type=int, default=3)
    args = parser.parse_args()
    start = date.fromisoformat(args.start) if args.start else datetime.now(ZoneInfo("Europe/Warsaw")).date()
    print("\n".join(scan_dates(start, args.days)))

if __name__ == "__main__":
    main()
