#!/usr/bin/env python3
"""
Alpha Pulse — Full Automation Engine
"""
import os
import sys
import os
import json
from datetime import datetime

# Import all modules
sys.path.insert(0, os.path.dirname(__file__))
from subscriber_db import init_db, get_active_subscribers, save_scan, add_pick, get_latest_scan, compute_win_rate
from telegram_bot import send_message, broadcast_to_subscribers, format_scan_for_telegram
import yfinance as yf

def run_scan():
    """Full market scan"""
    TICKERS = ['NVDA', 'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'AMD', 'SOFI', 'PLTR', 'SPY', 'QQQ']
    results = {}
    
    def calc_rsi(data, period=14):
        delta = data.diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss
        return round((100 - (100 / (1 + rs))).iloc[-1], 1)
    
    def calc_macd(data):
        ema12 = data.ewm(span=12).mean()
        ema26 = data.ewm(span=26).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9).mean()
        return 'BULLISH' if macd.iloc[-1] > signal.iloc[-1] else 'BEARISH'
    
    for t in TICKERS:
        try:
            stock = yf.Ticker(t)
            hist = stock.history(period='3mo')
            if len(hist) < 50:
                continue
            price = round(hist['Close'].iloc[-1], 2)
            rsi = calc_rsi(hist['Close'])
            macd = calc_macd(hist['Close'])
            sma20 = round(hist['Close'].rolling(20).mean().iloc[-1], 2)
            sma50 = round(hist['Close'].rolling(50).mean().iloc[-1], 2)
            high = round(hist['High'].rolling(252).max().iloc[-1], 2)
            low = round(hist['Low'].rolling(252).min().iloc[-1], 2)
            support = round(low + (price - low) * 0.236, 2)
            resistance = round(high - (high - price) * 0.236, 2)
            trend = 'UPTREND' if sma20 > sma50 else 'DOWNTREND'
            signal = 'HOLD'
            if rsi < 35 and macd == 'BULLISH': signal = 'BUY'
            elif rsi > 70 and macd == 'BEARISH': signal = 'SELL'
            results[t] = {
                'price': price, 'rsi': rsi, 'macd': macd, 'signal': signal,
                'trend': trend, 'sma20': sma20, 'sma50': sma50,
                'support': support, 'resistance': resistance
            }
        except:
            results[t] = {'error': 'scan_failed'}
    
    output = {'tickers': results, 'scanned_at': datetime.utcnow().isoformat()}
    
    # Save locally
    with open('scan_results.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    # Save to DB
    save_scan(output)
    for t, d in results.items():
        if d.get('signal') == 'BUY':
            add_pick(t, 'buy', d['price'], f"RSI {d['rsi']}, MACD {d['macd']}")
    
    return output

def deploy_site():
    """Deploy current index.html to Vercel"""
    VC_TOKEN = os.environ.get("VERCEL_TOKEN", "")
    
    import urllib.request, time
    
    with open('index.html', 'rb') as f:
        content = f.read()
    
    payload = json.dumps({
        "name": "alpha-pulse",
        "files": [{"file": "index.html", "data": content.decode('utf-8')}],
        "target": "production"
    }).encode()
    
    req = urllib.request.Request(
        "https://api.vercel.com/v12/deployments",
        data=payload,
        headers={"Authorization": f"Bearer {VC_TOKEN}", "Content-Type": "application/json"},
        method="POST"
    )
    
    resp = json.loads(urllib.request.urlopen(req, timeout=30).read())
    url = f"https://{resp.get('url', '?')}"
    time.sleep(10)
    return url

def send_daily_report(scan_data):
    """Send daily report to all subscribers"""
    print("\nSending reports to subscribers...")
    
    init_db()
    free_subs = get_active_subscribers('free')
    premium_subs = get_active_subscribers('premium')
    all_subs = free_subs + premium_subs
    
    if not all_subs:
        print("  No subscribers yet")
        return
    
    # Format the main report
    report = format_scan_for_telegram(scan_data)
    
    # We store telegram IDs manually - for now send to known chats
    # In production, store telegram_id in subscriber DB
    known_chats = {'8710537854': 'Ho Ba'}
    
    sent = 0
    for chat_id, name in known_chats.items():
        ok = send_message(chat_id, report)
        if ok:
            sent += 1
            print(f"  ✓ Sent to {name} ({chat_id})")
        else:
            print(f"  ✗ Failed to send to {name} ({chat_id})")
    
    print(f"  Reports sent: {sent}/{len(known_chats)}")
    return sent

if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'all'
    
    if mode == 'scan':
        scan = run_scan()
        print(f"Scan complete: {len([v for v in scan['tickers'].values() if 'error' not in v])} tickers")
    
    elif mode == 'report':
        scan = get_latest_scan()
        if scan:
            report_text = format_scan_for_telegram(scan.get('data', {}))
            print(report_text)
    
    elif mode == 'broadcast':
        scan = get_latest_scan()
        if scan:
            send_daily_report(scan.get('data', {}))
        else:
            print("No scan data found. Run 'scan' first.")
    
    elif mode == 'all':
        print(f"=== Alpha Pulse Auto-Run ===")
        print(f"{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
        print("=" * 35)
        
        # 1. Scan
        print("\n1. Running market scan...")
        scan = run_scan()
        scan_count = len([v for v in scan['tickers'].values() if 'error' not in v])
        print(f"   {scan_count} tickers scanned")
        
        # 2. Generate index.html
        print("\n2. Deploying site...")
        try:
            url = deploy_site()
            print(f"   Deployed: {url}")
        except Exception as e:
            print(f"   Deploy failed: {e}")
        
        # 3. Send report
        print("\n3. Sending reports...")
        send_daily_report(scan)
        
        # 4. Stats
        init_db()
        stats_r = compute_win_rate()
        print(f"\n   Track record: {stats_r['wins']}W / {stats_r['losses']}L ({stats_r['win_rate']}%)")
        
        print("\n✓ Auto-run complete")
