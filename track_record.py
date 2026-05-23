#!/usr/bin/env python3
"""Track record system — logs picks and checks performance."""
import json, os
from datetime import datetime, timedelta
import yfinance as yf

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TRACK_FILE = os.path.join(BASE_DIR, 'track_record.json')
SCAN_FILE = os.path.join(BASE_DIR, 'scan_results.json')


def init_track_record():
    if not os.path.exists(TRACK_FILE):
        data = {
            'created_at': datetime.utcnow().isoformat(),
            'picks': [],
            'stats': {'total_picks': 0, 'correct': 0, 'incorrect': 0, 'win_rate': 0}
        }
        with open(TRACK_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        return data

    with open(TRACK_FILE) as f:
        return json.load(f)


def log_daily_picks(scan_data):
    """Log today's picks."""
    track = init_track_record()

    # Get BUY signals
    buys = []
    for t, d in scan_data['tickers'].items():
        if isinstance(d, dict) and d.get('signal') == 'BUY':
            buys.append({'ticker': t, 'entry_price': d['price'], 'rsi': d['rsi']})

    today = datetime.utcnow().strftime('%Y-%m-%d')

    # Don't re-log if already logged today
    existing_dates = [p['date'] for p in track['picks']]
    if today in existing_dates:
        return track

    if buys:
        entry = {
            'date': today,
            'picks': buys,
            'status': 'open'
        }
        track['picks'].append(entry)
        track['stats']['total_picks'] += len(buys)

    with open(TRACK_FILE, 'w') as f:
        json.dump(track, f, indent=2)

    return track


def check_closed_picks():
    """Check 7-day-old picks for performance."""
    track = init_track_record()
    now = datetime.utcnow()

    for pick in track['picks']:
        if pick.get('status') != 'open':
            continue

        pick_date = datetime.strptime(pick['date'], '%Y-%m-%d')
        if (now - pick_date).days < 5:
            continue

        # Check each ticker
        for p in pick['picks']:
            try:
                stock = yf.Ticker(p['ticker'])
                hist = stock.history(period='7d', interval='1d')
                if hist.empty:
                    continue
                current_price = hist['Close'].iloc[-1]
                entry = p['entry_price']
                change_pct = round((current_price - entry) / entry * 100, 2)
                p['exit_price'] = round(current_price, 2)
                p['return_pct'] = change_pct

                if change_pct > 0:
                    track['stats']['correct'] += 1
                else:
                    track['stats']['incorrect'] += 1
            except:
                continue

        pick['status'] = 'closed'
        pick['checked_at'] = now.isoformat()

    total = track['stats']['correct'] + track['stats']['incorrect']
    if total > 0:
        track['stats']['win_rate'] = round(track['stats']['correct'] / total * 100, 1)

    with open(TRACK_FILE, 'w') as f:
        json.dump(track, f, indent=2)

    return track


if __name__ == '__main__':
    import sys

    if os.path.exists(SCAN_FILE):
        with open(SCAN_FILE) as f:
            scan = json.load(f)
        log_daily_picks(scan)

    check_closed_picks()

    with open(TRACK_FILE) as f:
        track = json.load(f)

    wins = track['stats']['correct']
    total = track['stats']['correct'] + track['stats']['incorrect']
    rate = track['stats']['win_rate']

    print(f"Track Record:")
    print(f"  Picks tracked: {track['stats']['total_picks']}")
    print(f"  Closed: {total}")
    print(f"  Win rate: {rate}% ({wins}/{total})")
    print(f"  Open positions: {track['stats']['total_picks'] - total}")
