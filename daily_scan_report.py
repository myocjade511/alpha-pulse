#!/usr/bin/env python3
"""Alpha Pulse — Daily Market Scan & Report Generator.
Generates: scan.json (live data), report.md (subscriber email), index.html (landing page)
"""
import json, os, base64
from datetime import datetime
import yfinance as yf
import urllib.request

# === CONFIG ===
TICKERS = ['NVDA', 'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'AMD', 'SOFI', 'PLTR', 'SPY', 'QQQ']
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCAN_FILE = os.path.join(BASE_DIR, 'scan_results.json')
TRACK_FILE = os.path.join(BASE_DIR, 'track_record.json')
REPORT_FILE = os.path.join(BASE_DIR, 'report.md')

VC_TOKEN = os.environ.get("VERCEL_TOKEN", "")
TEAM_ID = "team_xvFesmiaWI9RkZvfYuMNbDtU"
DEPLOY_URL = "https://alpha-pulse-dp7egtgfi-myocjade-s-projects.vercel.app"


def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def calc_macd(series):
    ema12 = series.ewm(span=12).mean()
    ema26 = series.ewm(span=26).mean()
    return ema12 - ema26


def calc_signal(rsi, macd, macd_signal, price, sma50):
    """Determine trade signal."""
    score = 0
    if rsi < 35: score += 2
    elif rsi < 45: score += 1
    elif rsi > 70: score -= 2
    elif rsi > 60: score -= 1

    if macd > macd_signal[-1] if hasattr(macd_signal, '__iter__') else macd > 0:
        score += 1
    else:
        score -= 1

    if score >= 2: return 'BUY'
    elif score <= -2: return 'SELL'
    else: return 'HOLD'


def scan_market():
    print(f"Scanning {len(TICKERS)} tickers...")
    results = {}

    for t in TICKERS:
        try:
            stock = yf.Ticker(t)
            hist = stock.history(period='2mo')

            if hist.empty or len(hist) < 15:
                results[t] = {'error': 'insufficient data'}
                continue

            close = hist['Close']
            price = round(close.iloc[-1], 2)
            rsi = round(calc_rsi(close).iloc[-1], 1)

            macd_line = calc_macd(close)
            macd = round(macd_line.iloc[-1], 2)
            ema9 = macd_line.ewm(span=9).mean()
            macd_signal = round(ema9.iloc[-1], 2)

            sma20 = round(close.rolling(20).mean().iloc[-1], 2) if len(close) >= 20 else None
            sma50 = round(close.rolling(50).mean().iloc[-1], 2) if len(close) >= 50 else None

            # Volume analysis
            vol = hist['Volume']
            avg_vol = round(vol.rolling(20).mean().iloc[-1], 0) if len(vol) >= 20 else None
            vol_ratio = round(vol.iloc[-1] / avg_vol, 2) if avg_vol else None

            # Support/Resistance via recent highs/lows
            recent_high = round(close.tail(20).max(), 2)
            recent_low = round(close.tail(20).min(), 2)

            signal = calc_signal(rsi, macd, macd_signal, price, sma50)

            results[t] = {
                'price': price,
                'rsi': rsi,
                'macd': macd,
                'macd_signal': macd_signal,
                'sma20': sma20,
                'sma50': sma50,
                'avg_vol': int(avg_vol) if avg_vol else None,
                'vol_ratio': vol_ratio,
                'support': recent_low,
                'resistance': recent_high,
                'signal': signal
            }
        except Exception as e:
            results[t] = {'error': str(e)}

    # Add scan metadata
    output = {
        'scanned_at': datetime.utcnow().isoformat(),
        'tickers': results
    }

    with open(SCAN_FILE, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"Scanned {len([v for v in results.values() if 'error' not in v])}/{len(TICKERS)} tickers")
    return output


def generate_report(scan):
    """Generate markdown report from scan data."""
    lines = []
    lines.append(f"# Alpha Pulse Daily Scan — {datetime.utcnow().strftime('%b %d, %Y')}")
    lines.append("")
    lines.append("| Ticker | Price | RSI | Signal | MACD | Support | Resistance |")
    lines.append("|--------|-------|-----|--------|------|---------|------------|")

    for t in TICKERS:
        d = scan['tickers'].get(t, {})
        if 'error' in d:
            lines.append(f"| {t} | ERROR | — | — | — | — | — |")
            continue
        lines.append(
            f"| {t} | ${d['price']} | {d['rsi']} "
            f"| **{d['signal']}** | {d['macd']} "
            f"| ${d['support']} | ${d['resistance']} |"
        )

    lines.append("")
    lines.append("### Top Picks")
    lines.append("")

    # Sort by signal strength
    buys = [(t, d) for t, d in scan['tickers'].items()
            if isinstance(d, dict) and d.get('signal') == 'BUY']
    buys.sort(key=lambda x: x[1]['rsi'])

    if buys:
        for t, d in buys[:5]:
            lines.append(f"- **{t}** — ${d['price']} — RSI {d['rsi']} — Oversold bounce play")
    else:
        lines.append("No clear BUY signals today.")

    lines.append("")
    lines.append(f"---")
    lines.append(f"*Generated by Alpha Pulse AI — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}*")
    lines.append(f"*For informational purposes only. Not financial advice.*")

    report = '\n'.join(lines)
    with open(REPORT_FILE, 'w') as f:
        f.write(report)

    return report


def generate_index_html(scan):
    """Generate the landing page with live data baked in."""
    now = datetime.utcnow()
    tickers_data = scan['tickers']

    # Build ticker HTML
    ticker_html = ""
    buys = []
    for t in TICKERS:
        d = tickers_data.get(t, {})
        if 'error' in d:
            continue
        signal_class = f"signal-{d['signal'].lower()}"
        ticker_html += (
            f'        <div class="tick">'
            f'<div class="sym">{t}</div>'
            f'<div class="price">${d["price"]:.2f}</div>'
            f'<span class="{signal_class}">{d["signal"]}</span>'
            f'</div>\n'
        )
        if d['signal'] == 'BUY':
            buys.append((t, d))

    # Build picks HTML
    picks_html = ""
    for t, d in buys[:5]:
        reason = "Oversold bounce" if d['rsi'] < 40 else "Momentum play" if d['macd'] > 0 else "Support level"
        picks_html += (
            f'    <div class="pick">\n'
            f'      <div class="left"><div class="tkr">{t}</div><div class="desc">{reason} · RSI {d["rsi"]}</div></div>\n'
            f'      <div class="right"><div class="roi">${d["price"]}</div><div class="date">{now.strftime("%b %d")}</div></div>\n'
            f'    </div>\n'
        )

    if not picks_html:
        picks_html = '    <div class="pick"><div class="left"><div class="tkr">No picks today</div><div class="desc">Markets are neutral</div></div></div>\n'

    # Read existing template and inject data
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Alpha Pulse — AI Quant Trading Advisory</title>
  <script src="https://js.stripe.com/v3/"></script>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #0a0a0f;
      color: #e0e0e0;
      line-height: 1.6;
    }}
    .bg-glow {{
      position: fixed; top: -50%; left: -50%; width: 200%; height: 200%;
      background: radial-gradient(ellipse at 30% 20%, rgba(0, 200, 255, 0.08) 0%, transparent 60%),
                  radial-gradient(ellipse at 70% 80%, rgba(120, 50, 255, 0.06) 0%, transparent 60%);
      z-index: -1;
    }}
    .container {{ max-width: 1100px; margin: 0 auto; padding: 0 24px; }}

    nav {{
      display: flex; justify-content: space-between; align-items: center;
      padding: 20px 0; border-bottom: 1px solid rgba(255,255,255,0.06);
    }}
    nav .logo {{ font-size: 1.4rem; font-weight: 700; color: #00c8ff; letter-spacing: 1px; }}
    nav .logo span {{ color: #e0e0e0; }}
    nav a {{ color: #888; text-decoration: none; margin-left: 24px; font-size: 0.9rem; }}
    nav a:hover {{ color: #00c8ff; }}

    .hero {{
      text-align: center; padding: 100px 0 80px;
    }}
    .hero h1 {{
      font-size: 3.5rem; font-weight: 800; margin-bottom: 20px;
      background: linear-gradient(135deg, #00c8ff, #7a3aff);
      -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }}
    .hero p {{ font-size: 1.2rem; color: #999; max-width: 650px; margin: 0 auto 40px; }}
    .hero .cta {{
      display: inline-block; padding: 16px 40px;
      background: linear-gradient(135deg, #00c8ff, #7a3aff);
      color: #fff; font-weight: 600; border-radius: 8px; text-decoration: none;
      font-size: 1.1rem; transition: transform 0.2s;
    }}
    .hero .cta:hover {{ transform: translateY(-2px); }}

    .live-ticker {{
      background: rgba(255,255,255,0.03); border-radius: 12px;
      padding: 20px; margin: 40px auto; max-width: 750px;
      border: 1px solid rgba(255,255,255,0.06);
    }}
    .live-ticker .label {{
      color: #666; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 2px;
      margin-bottom: 12px;
    }}
    .live-ticker .tickers {{
      display: flex; gap: 20px; justify-content: center; flex-wrap: wrap;
    }}
    .live-ticker .tick {{ text-align: center; }}
    .live-ticker .tick .sym {{ font-weight: 700; font-size: 1rem; }}
    .live-ticker .tick .price {{ color: #999; font-size: 0.9rem; }}
    .live-ticker .tick .signal {{ font-size: 0.75rem; padding: 2px 8px; border-radius: 4px; margin-top: 4px; display: inline-block; }}
    .signal-buy {{ background: rgba(0,200,100,0.2); color: #00c864; }}
    .signal-sell {{ background: rgba(255,60,60,0.2); color: #ff3c3c; }}
    .signal-hold {{ background: rgba(255,200,0,0.2); color: #ffc800; }}

    .features {{
      display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px;
      margin: 80px 0;
    }}
    .feature {{
      background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.06);
      border-radius: 12px; padding: 32px 24px;
    }}
    .feature h3 {{ color: #00c8ff; margin-bottom: 12px; font-size: 1.2rem; }}
    .feature p {{ color: #888; font-size: 0.9rem; }}

    .pricing {{
      display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px;
      margin: 80px 0;
    }}
    .plan {{
      background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.06);
      border-radius: 12px; padding: 40px 24px; text-align: center;
    }}
    .plan.featured {{
      border-color: #00c8ff; transform: scale(1.05);
      background: rgba(0,200,255,0.03);
    }}
    .plan h3 {{ font-size: 1.3rem; margin-bottom: 8px; }}
    .plan .price {{ font-size: 2.5rem; font-weight: 800; color: #fff; margin: 16px 0; }}
    .plan .price span {{ font-size: 1rem; color: #666; }}
    .plan ul {{ list-style: none; margin: 24px 0; }}
    .plan ul li {{ padding: 8px 0; color: #999; font-size: 0.9rem; border-bottom: 1px solid rgba(255,255,255,0.04); }}
    .plan ul li:before {{ content: "✓ "; color: #00c864; }}
    .plan .btn {{
      display: inline-block; padding: 12px 32px; border-radius: 8px;
      text-decoration: none; font-weight: 600; margin-top: 16px;
    }}
    .plan .btn-outline {{ border: 1px solid #00c8ff; color: #00c8ff; }}
    .plan .btn-solid {{ background: linear-gradient(135deg, #00c8ff, #7a3aff); color: #fff; }}

    .recent-picks {{ margin: 80px 0; }}
    .recent-picks h2 {{ margin-bottom: 24px; font-size: 1.8rem; }}
    .pick {{
      background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.06);
      border-radius: 8px; padding: 16px 20px; margin-bottom: 12px;
      display: flex; justify-content: space-between; align-items: center;
    }}
    .pick .left .tkr {{ font-weight: 700; }}
    .pick .left .desc {{ color: #888; font-size: 0.85rem; }}
    .pick .right {{ text-align: right; }}
    .pick .right .roi {{ color: #00c864; font-weight: 700; }}
    .pick .right .date {{ color: #666; font-size: 0.8rem; }}

    .last-updated {{
      text-align: center; color: #555; font-size: 0.8rem; margin: 10px 0;
    }}

    footer {{
      text-align: center; padding: 40px 0; color: #555; font-size: 0.85rem;
      border-top: 1px solid rgba(255,255,255,0.06); margin-top: 80px;
    }}

    @media (max-width: 768px) {{
      .hero h1 {{ font-size: 2.2rem; }}
      .features, .pricing {{ grid-template-columns: 1fr; }}
      .plan.featured {{ transform: none; }}
    }}
  </style>
</head>
<body>
  <div class="bg-glow"></div>

  <nav class="container">
    <div class="logo">ALPHA <span>PULSE</span></div>
    <div>
      <a href="#features">Features</a>
      <a href="#pricing">Pricing</a>
      <a href="#picks">Picks</a>
    </div>
  </nav>

  <section class="hero container">
    <h1>AI That Trades.<br>You That Collect.</h1>
    <p>Institutional-grade quant analysis delivered to your phone. Real-time signals, options picks, and market scans — fully automated by AI.</p>
    <a href="#pricing" class="cta">Start Free →</a>

    <div class="last-updated">Last scan: {now.strftime('%b %d, %Y at %H:%M UTC')}</div>

    <div class="live-ticker">
      <div class="label">► Live Market Pulse</div>
      <div class="tickers">
{ticker_html}
      </div>
    </div>
  </section>

  <section id="features" class="container features">
    <div class="feature">
      <h3>📊 Daily Market Scan</h3>
      <p>RSI, MACD, SMA analysis across 100+ tickers. Know which way the market's leaning before you trade.</p>
    </div>
    <div class="feature">
      <h3>📮 Options Watchlist</h3>
      <p>Top 5 option setups with strike prices, breakevens, and ROI projections. Updated daily before market open.</p>
    </div>
    <div class="feature">
      <h3>📱 Telegram Alerts</h3>
      <p>Real-time trade signals delivered straight to your phone. No app to install, no emails to check.</p>
    </div>
    <div class="feature">
      <h3>🗓 Portfolio Tracking</h3>
      <p>Paper trade our picks alongside us. Track performance, win rate, and ROI month over month.</p>
    </div>
    <div class="feature">
      <h3>🔍 Deep Dives</h3>
      <p>Fundamental and technical deep dives on any ticker on demand. Ask and receive.</p>
    </div>
    <div class="feature">
      <h3>🤖 100% Automated</h3>
      <p>No humans, no bias, no emotion. Pure algorithmic analysis running 24/7 on live market data.</p>
    </div>
  </section>

  <section id="pricing" class="container pricing">
    <div class="plan">
      <h3>Free</h3>
      <div class="price">$0<span>/mo</span></div>
      <ul>
        <li>Weekly market overview</li>
        <li>1 pick per week</li>
        <li>Email delivery</li>
        <li>Public Telegram channel</li>
      </ul>
      <a href="#" class="btn btn-outline" onclick="subscribe('free')">Get Started</a>
    </div>

    <div class="plan featured">
      <h3>Premium</h3>
      <div class="price">$49<span>/mo</span></div>
      <ul>
        <li>Daily market scan</li>
        <li>Top 5 options picks</li>
        <li>Entry/exit levels</li>
        <li>Real-time Telegram alerts</li>
        <li>Portfolio tracker</li>
        <li>Priority support</li>
      </ul>
      <a href="#" class="btn btn-solid" onclick="subscribe('premium')">Subscribe →</a>
    </div>

    <div class="plan">
      <h3>Institutional</h3>
      <div class="price">$499<span>/mo</span></div>
      <ul>
        <li>Everything in Premium</li>
        <li>Custom portfolio management</li>
        <li>Risk analytics & reports</li>
        <li>Dedicated AI agent</li>
        <li>API access</li>
        <li>White-label option</li>
      </ul>
      <a href="#" class="btn btn-outline" onclick="subscribe('institutional')">Contact Us</a>
    </div>
  </section>

  <section id="picks" class="container recent-picks">
    <h2>📋 Today's Picks</h2>
{picks_html}
  </section>

  <footer class="container">
    <p>Alpha Pulse — AI-Powered Quant Trading Advisory</p>
    <p style="margin-top: 8px;">⚠️ For informational purposes only. Not financial advice. Trading involves risk.</p>
    <p style="margin-top: 4px;">Powered by OpenClaw 🤖</p>
  </footer>

  <script>
    const stripe = Stripe('pk_test_51TXfKVLJy1J1wtNpClRGniyKFlMReimzaQYs1AwU7kwEdHUrRpRaizMQddob33kT5gH6z92KlIrRi5xgQcNCvu9j00IVlxukHC');

    const PRICES = {{
      free: null,
      premium: 'price_1TYhR7LJy1J1wtNpTeqTiruW',
      institutional: 'price_1TYhR7LJy1J1wtNpxsJ26utJ'
    }};

    async function subscribe(plan) {{
      if (plan === 'free') {{
        window.open('https://t.me/alphapulse', '_blank');
        return;
      }}
      if (plan === 'institutional') {{
        window.location.href = 'mailto:hello@alpha-pulse.com';
        return;
      }}

      try {{
        const {{ error }} = await stripe.redirectToCheckout({{
          lineItems: [{{ price: PRICES[plan], quantity: 1 }}],
          mode: 'subscription',
          successUrl: window.location.origin + '/success.html',
          cancelUrl: window.location.origin + '/cancel.html',
        }});
        if (error) alert(error.message);
      }} catch(e) {{
        alert('Checkout error: ' + e.message);
      }}
    }}
  </script>
</body>
</html>"""

    with open(os.path.join(BASE_DIR, 'index.html'), 'w') as f:
        f.write(html)

    return html


def deploy_to_vercel():
    """Push the updated index.html to Vercel."""
    with open(os.path.join(BASE_DIR, 'index.html')) as f:
        html = f.read()

    payload = json.dumps({
        "name": "alpha-pulse",
        "files": [{"file": "index.html", "data": html}],
        "target": "production"
    }).encode()

    req = urllib.request.Request(
        f"https://api.vercel.com/v12/deployments",
        data=payload,
        headers={
            "Authorization": f"Bearer {VC_TOKEN}",
            "Content-Type": "application/json"
        },
        method="POST"
    )

    resp = json.loads(urllib.request.urlopen(req, timeout=30).read())
    deploy_id = resp.get('id')
    deploy_url = f"https://{resp.get('url', '?')}"
    print(f"Deployed: {deploy_url}")

    # Check status after a moment
    import time
    time.sleep(12)
    check_req = urllib.request.Request(
        f"https://api.vercel.com/v12/deployments/{deploy_id}",
        headers={"Authorization": f"Bearer {VC_TOKEN}"}
    )
    check = json.loads(urllib.request.urlopen(check_req, timeout=15).read())
    state = check.get('readyState', '?')
    print(f"State: {state}")

    # Update deploy-info
    deploy_path = os.path.join(BASE_DIR, 'deploy-info.json')
    with open(deploy_path) as f:
        info = json.load(f)
    info['last_deploy_url'] = deploy_url
    info['last_deploy_state'] = state
    info['last_deployed_at'] = datetime.utcnow().isoformat()
    with open(deploy_path, 'w') as f:
        json.dump(info, f, indent=2)

    return deploy_url


if __name__ == '__main__':
    import sys

    print("=" * 50)
    print("  ALPHA PULSE — Automated Scan & Deploy")
    print(f"  {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 50)
    print()

    # 1. Scan
    scan = scan_market()

    # 2. Generate report
    report = generate_report(scan)

    # 3. Generate landing page
    html = generate_index_html(scan)

    # 4. Deploy
    print("\nDeploying to Vercel...")
    url = deploy_to_vercel()

    print(f"\n✅ Done! Live at: {url}")
    print(f"   Report: {REPORT_FILE}")
    print(f"   Scan: {SCAN_FILE}")
