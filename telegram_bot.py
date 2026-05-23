#!/usr/bin/env python3
"""
Alpha Pulse — Telegram Broadcast Engine
Sends reports and alerts to subscribers via Telegram bot.
"""
import urllib.request
import urllib.parse
import json
import os

BOT_TOKEN = "8711439519:AAHtMuEmsbTUl44onFjCiUfQRxzKpI8FtO0"

def send_message(chat_id, text, parse_mode='Markdown'):
    """Send a text message to a Telegram chat."""
    data = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': parse_mode,
        'disable_web_page_preview': True
    }
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    req = urllib.request.Request(url, json.dumps(data).encode(), 
        {'Content-Type': 'application/json'})
    try:
        resp = json.loads(urllib.request.urlopen(req, timeout=15).read())
        return resp.get('ok', False)
    except Exception as e:
        print(f"  Telegram send error: {e}")
        return False

def broadcast_to_subscribers(text, subscriber_chat_ids):
    """Send a message to all subscriber chat IDs."""
    results = []
    for chat_id in subscriber_chat_ids:
        ok = send_message(chat_id, text)
        results.append((chat_id, ok))
        # Rate limit: max 20 msg/min
        import time
        time.sleep(0.3)
    return results

def format_scan_for_telegram(scan_data):
    """Format scan results as a Telegram message."""
    tickers = scan_data.get('tickers', {})
    now = __import__('datetime').datetime.utcnow().strftime('%b %d, %Y %H:%M UTC')
    
    buys = [(t, d) for t, d in tickers.items() if d.get('signal') == 'BUY']
    sells = [(t, d) for t, d in tickers.items() if d.get('signal') == 'SELL']
    holds = [(t, d) for t, d in tickers.items() if d.get('signal') == 'HOLD']
    
    lines = [f"📈 *Alpha Pulse — Daily Scan*", f"_{now}_", ""]
    lines.append(f"BUY {len(buys)} · SELL {len(sells)} · HOLD {len(holds)}")
    lines.append("")
    
    if buys:
        lines.append("*🎯 Top Buys:*")
        for t, d in sorted(buys, key=lambda x: x[1]['rsi'])[:5]:
            lines.append(f"🟢 *{t}* ${d['price']} — RSI {d['rsi']} | {d['trend']}")
        lines.append("")
    
    if sells:
        lines.append("*🔴 Overbought / Caution:*")
        for t, d in sells[:3]:
            lines.append(f"🔴 *{t}* ${d['price']} (RSI {d['rsi']})")
        lines.append("")
    
    # Top tickers table
    lines.append("`Portfolio Pulse:`")
    order = ['NVDA', 'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'AMD', 'SOFI', 'PLTR', 'SPY', 'QQQ']
    for t in order:
        d = tickers.get(t, {})
        if 'error' in d:
            continue
        icon = {'BUY': '🟢', 'SELL': '🔴', 'HOLD': '⚪'}.get(d['signal'], '⚪')
        lines.append(f"{icon} {t} ${d['price']} RSI {d['rsi']} · {d['signal']} · {d['trend']}")
    
    lines.append("")
    lines.append("⚠️ Not financial advice.")
    
    return '\n'.join(lines)

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        # Test send to a chat ID
        chat_id = sys.argv[2] if len(sys.argv) > 2 else '8710537854'
        ok = send_message(chat_id, "🔔 *Alpha Pulse Test* — Bot is alive!")
        print(f"Test message sent: {ok}")
