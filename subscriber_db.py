#!/usr/bin/env python3
"""
Alpha Pulse — Subscriber Database & Email Engine
SQLite backend for managing free-tier subscribers.
No external dependencies, pure stdlib.
"""

import sqlite3
import json
import smtplib
import email.mime.text
import email.mime.multipart
import os
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = os.path.join(os.path.dirname(__file__), 'subscribers.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS subscribers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            telegram_id TEXT,
            name TEXT,
            tier TEXT DEFAULT 'free',
            status TEXT DEFAULT 'active',
            source TEXT DEFAULT 'web',
            subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_sent_at TIMESTAMP,
            unsubscribed_at TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS picks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            signal TEXT NOT NULL,
            entry_price REAL,
            current_price REAL,
            exit_price REAL,
            direction TEXT DEFAULT 'long',
            status TEXT DEFAULT 'open',
            reason TEXT,
            opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            closed_at TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            sent_count INTEGER DEFAULT 0,
            open_count INTEGER DEFAULT 0,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS daily_scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_date DATE UNIQUE,
            data TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_sub_status ON subscribers(status);
        CREATE INDEX IF NOT EXISTS idx_picks_status ON picks(status);
    """)
    conn.commit()
    conn.close()
    print("✅ Database initialized at", DB_PATH)

def add_subscriber(email, name=None, source='web', telegram_id=None):
    conn = get_db()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO subscribers (email, name, source, telegram_id) VALUES (?, ?, ?, ?)",
            (email, name, source, telegram_id)
        )
        conn.commit()
        # Check if inserted
        cur = conn.execute("SELECT id, email FROM subscribers WHERE email = ?", (email,))
        row = cur.fetchone()
        conn.close()
        return row is not None
    except Exception as e:
        conn.close()
        return False

def get_active_subscribers(tier='free'):
    conn = get_db()
    cur = conn.execute(
        "SELECT * FROM subscribers WHERE status = 'active' AND tier = ? ORDER BY subscribed_at DESC",
        (tier,)
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def save_scan(scan_data):
    conn = get_db()
    today = datetime.utcnow().strftime('%Y-%m-%d')
    try:
        conn.execute(
            "INSERT OR REPLACE INTO daily_scans (scan_date, data) VALUES (?, ?)",
            (today, json.dumps(scan_data))
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        conn.close()
        return False

def get_latest_scan():
    conn = get_db()
    cur = conn.execute("SELECT * FROM daily_scans ORDER BY scan_date DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()
    if row:
        return {'date': row['scan_date'], 'data': json.loads(row['data'])}
    return None

def add_pick(ticker, signal, entry_price, reason=None):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO picks (ticker, signal, entry_price, reason) VALUES (?, ?, ?, ?)",
            (ticker, signal, entry_price, reason)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        conn.close()
        return False

def get_picks(status='open'):
    conn = get_db()
    cur = conn.execute(
        "SELECT * FROM picks WHERE status = ? ORDER BY opened_at DESC",
        (status,)
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def compute_win_rate():
    conn = get_db()
    cur = conn.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN signal = 'buy' AND exit_price > entry_price THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN signal = 'sell' AND exit_price < entry_price THEN 1 ELSE 0 END) as wins_sell
        FROM picks WHERE status = 'closed'
    """)
    row = cur.fetchone()
    total = row['total'] or 0
    wins = (row['wins'] or 0) + (row['wins_sell'] or 0)
    conn.close()
    return {
        'total': total,
        'wins': wins,
        'losses': total - wins,
        'win_rate': round(wins / total * 100, 1) if total > 0 else 0
    }


def send_free_email(subject, html_body, text_body=None):
    """Send email to all active free subscribers using SMTP."""
    subscribers = get_active_subscribers('free')
    if not subscribers:
        print("No active subscribers to send to")
        return
    
    # Check if SMTP is configured
    smtp_host = os.environ.get('SMTP_HOST')
    smtp_port = int(os.environ.get('SMTP_PORT', '587'))
    smtp_user = os.environ.get('SMTP_USER')
    smtp_pass = os.environ.get('SMTP_PASS')
    from_email = os.environ.get('FROM_EMAIL', 'alpha@alpha-pulse.com')
    
    if not all([smtp_host, smtp_user, smtp_pass]):
        print("SMTP not configured. Subscribers registered but cannot send email.")
        print(f"  Set SMTP_HOST, SMTP_USER, SMTP_PASS env vars")
        print(f"  {len(subscribers)} subscribers waiting for emails")
        return
    
    conn = get_db()
    sent = 0
    for sub in subscribers:
        try:
            msg = email.mime.multipart.MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = from_email
            msg['To'] = sub['email']
            
            if text_body:
                msg.attach(email.mime.text.MIMEText(text_body, 'plain'))
            msg.attach(email.mime.text.MIMEText(html_body, 'html'))
            
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
            
            conn.execute("UPDATE subscribers SET last_sent_at = CURRENT_TIMESTAMP WHERE id = ?", (sub['id'],))
            sent += 1
        except Exception as e:
            print(f"  Failed to send to {sub['email']}: {e}")
    
    # Log the email
    conn.execute(
        "INSERT INTO emails (subject, body, sent_count) VALUES (?, ?, ?)",
        (subject, html_body[:500], sent)
    )
    conn.commit()
    conn.close()
    print(f"  Sent to {sent}/{len(subscribers)} subscribers")


def generate_weekly_report(scan_data):
    """Generate HTML email for weekly free-tier report."""
    now = datetime.utcnow().strftime('%b %d, %Y')
    tickers = scan_data.get('tickers', {})
    
    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><style>
body {{ font-family: -apple-system, sans-serif; background: #0a0a0f; color: #e0e0e0; padding: 20px; }}
.container {{ max-width: 600px; margin: 0 auto; }}
.header {{ text-align: center; padding: 30px 0; border-bottom: 1px solid rgba(255,255,255,0.1); }}
.header h1 {{ color: #00c8ff; font-size: 24px; }}
.tagline {{ color: #666; font-size: 14px; }}
.section {{ margin: 24px 0; padding: 16px; background: rgba(255,255,255,0.02); border-radius: 12px; border: 1px solid rgba(255,255,255,0.06); }}
.section h2 {{ color: #00c8ff; font-size: 18px; margin-bottom: 12px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
th {{ text-align: left; padding: 8px; color: #666; border-bottom: 1px solid rgba(255,255,255,0.06); }}
td {{ padding: 8px; border-bottom: 1px solid rgba(255,255,255,0.03); }}
.buy {{ color: #00c864; }}
.sell {{ color: #ff3c3c; }}
.hold {{ color: #ffc800; }}
.footer {{ text-align: center; padding: 20px; color: #555; font-size: 12px; border-top: 1px solid rgba(255,255,255,0.06); margin-top: 30px; }}
.btn {{ display: inline-block; padding: 10px 24px; background: linear-gradient(135deg, #00c8ff, #7a3aff); color: #fff; text-decoration: none; border-radius: 6px; font-size: 14px; }}
</style></head>
<body>
<div class="container">
<div class="header">
<h1>📊 Alpha Pulse Weekly</h1>
<div class="tagline">{now} · Free Tier Report</div>
</div>"""

    # Market overview
    html += '<div class="section"><h2>📈 Market Overview</h2><table><tr><th>Ticker</th><th>Price</th><th>Signal</th><th>RSI</th><th>Support</th></tr>'
    for t, d in sorted(tickers.items()):
        if 'error' in d:
            continue
        signal_class = d['signal'].lower()
        html += f'<tr><td><strong>{t}</strong></td><td>${d["price"]}</td><td class="{signal_class}"><strong>{d["signal"]}</strong></td><td>{d["rsi"]}</td><td>${d["support"]}</td></tr>'
    html += '</table></div>'

    # Top picks
    html += '<div class="section"><h2>🎯 Top Picks This Week</h2>'
    buy_tickers = [t for t, d in tickers.items() if d.get('signal') == 'BUY' and 'error' not in d]
    if buy_tickers:
        html += '<ul>'
        for t in buy_tickers[:3]:
            d = tickers[t]
            html += f'<li><strong>{t}</strong> at ${d["price"]} — RSI {d["rsi"]}, momentum shifting</li>'
        html += '</ul>'
    else:
        html += '<p style="color:#888;">No strong buy signals this week. Holding cash is a position.</p>'
    html += '</div>'

    # CTA
    html += f"""<div style="text-align:center;margin:32px 0;">
<a href="https://alpha-pulse-ivj1xn0ir-myocjade-s-projects.vercel.app" class="btn">View Full Dashboard →</a>
</div>
<div class="footer">
<p>Alpha Pulse · AI Quant Trading Advisory</p>
<p>For informational purposes only. Not financial advice.</p>
<p><a href="#" style="color:#555;">Unsubscribe</a> anytime.</p>
</div>
</div></body></html>"""
    return html


def subscriber_stats():
    conn = get_db()
    cur = conn.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN tier='free' AND status='active' THEN 1 ELSE 0 END) as free_active,
            SUM(CASE WHEN tier='premium' AND status='active' THEN 1 ELSE 0 END) as premium_active,
            SUM(CASE WHEN status='unsubscribed' THEN 1 ELSE 0 END) as unsubscribed
        FROM subscribers
    """)
    row = dict(cur.fetchone())
    conn.close()
    return row


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'init':
        init_db()
    elif len(sys.argv) > 1 and sys.argv[1] == 'stats':
        init_db()
        stats = subscriber_stats()
        print("\n=== Subscriber Stats ===")
        for k, v in stats.items():
            print(f"  {k}: {v}")
    elif len(sys.argv) > 1 and sys.argv[1] == 'add':
        if len(sys.argv) > 2:
            init_db()
            email = sys.argv[2]
            name = sys.argv[3] if len(sys.argv) > 3 else None
            if add_subscriber(email, name):
                print(f"✅ Added {email}")
            else:
                print(f"Already exists: {email}")
    else:
        print("Usage:")
        print("  python3 subscriber_db.py init       # Create/initialize database")
        print("  python3 subscriber_db.py stats      # Show subscriber stats")
        print("  python3 subscriber_db.py add <email> [name]  # Add subscriber")
