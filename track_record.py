#!/usr/bin/env python3
"""
Alpha Pulse — Track Record Engine
Automatically tracks performance of all picks and computes win rate.
Runs as part of daily automation.
"""
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))
from subscriber_db import init_db, get_picks, compute_win_rate, get_latest_scan
import yfinance as yf

def update_open_picks():
    """Check open picks against current prices and close them."""
    init_db()
    open_picks = get_picks('open')
    
    if not open_picks:
        return {'updated': 0, 'closed': 0}
    
    import sqlite3
    from pathlib import Path
    DB_PATH = os.path.join(os.path.dirname(__file__), 'subscribers.db')
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    
    updated = 0
    closed = 0
    
    for pick in open_picks:
        try:
            stock = yf.Ticker(pick['ticker'])
            hist = stock.history(period='5d')
            current_price = round(hist['Close'].iloc[-1], 2)
            
            # Update current price
            conn.execute(
                "UPDATE picks SET current_price = ? WHERE id = ?",
                (current_price, pick['id'])
            )
            updated += 1
            
            # Check if we should close (10% above entry = win, 5% below = loss)
            entry = pick['entry_price']
            if entry and entry > 0:
                change_pct = (current_price - entry) / entry * 100
                
                # Close if pick has been open for 7+ days or hit target/stop
                opened = datetime.strptime(pick['opened_at'][:10], '%Y-%m-%d')
                days_open = (datetime.utcnow() - opened).days
                
                # Close conditions:
                # 1. Hit 8% gain target (BUY signal)
                # 2. Hit 5% loss stop
                # 3. Been open 14+ days (time decay)
                if change_pct >= 8 or change_pct <= -5 or days_open >= 14:
                    conn.execute(
                        "UPDATE picks SET status = 'closed', exit_price = ?, closed_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (current_price, pick['id'])
                    )
                    closed += 1
        
        except Exception as e:
            pass
    
    conn.commit()
    conn.close()
    
    return {'updated': updated, 'closed': closed}

def print_track_record():
    """Print the current track record."""
    init_db()
    stats = compute_win_rate()
    picks = get_picks('closed')
    open_p = get_picks('open')
    
    print(f"📊 **Alpha Pulse Track Record**")
    print(f"   Generated: {datetime.utcnow().strftime('%b %d, %Y')}")
    print()
    print(f"   Closed Trades: {stats['total']}")
    print(f"   Wins: {stats['wins']} ({stats['win_rate']}%)")
    print(f"   Losses: {stats['losses']}")
    print()
    
    if picks:
        print("   Recent Closed Picks:")
        for p in picks[-5:]:
            entry = p['entry_price']
            exit_p = p['exit_price']
            if entry and exit_p:
                roi = round((exit_p - entry) / entry * 100, 1)
                icon = '🟢' if roi > 0 else '🔴'
                print(f"   {icon} {p['ticker']} — {p['signal'].upper()} — Entry ${entry} → Exit ${exit_p} ({roi:+.1f}%)")
    
    if open_p:
        print()
        print(f"   Open Positions: {len(open_p)}")
        for p in open_p[:5]:
            entry = p['entry_price']
            current = p['current_price']
            if entry and current:
                change = round((current - entry) / entry * 100, 1)
                icon = '🟢' if change > 0 else '🔴'
                print(f"   {icon} {p['ticker']} — Entry ${entry} → Now ${current} ({change:+.1f}%)")
    
    return stats

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'update':
        result = update_open_picks()
        print(f"Updated: {result['updated']}, Closed: {result['closed']}")
    else:
        print_track_record()
