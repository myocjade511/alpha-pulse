# Alpha Pulse — AI-Powered Quant Trading Advisory

Institutional-grade quant analysis delivered to your phone. Fully automated by OpenClaw.

## Live Site
👉 https://alpha-pulse-iprj5v8fz-myocjade-s-projects.vercel.app

## System Components

| Component | Description | Schedule |
|-----------|-------------|----------|
| `daily_scan_report.py` | Full market scan + report + deploy | Daily (market open) |
| `track_record.py` | Tracks picks, checks performance | Daily |
| `deploy_latest.py` | Deploys latest index.html to Vercel | On demand |
| `index.html` | Landing page with live data | Auto-generated |

## Architecture

1. **Market Scan** — yfinance fetches live data for 12+ tickers
2. **Signal Generation** — RSI, MACD, SMA analysis determines BUY/HOLD/SELL
3. **Report Generation** — Markdown report with top picks, support/resistance
4. **Auto-Deploy** — Updated landing page pushed to Vercel with fresh data
5. **Track Record** — Win rate tracking on closed positions

## Subscription Tiers
- **Free** — $0/mo — Weekly overview, public channel
- **Premium** — $49/mo — Daily scans, top 5 picks, Telegram alerts
- **Institutional** — $499/mo — Everything + dedicated agent, API, white-label

## Tech Stack
- Python (yfinance, stdlib)
- Vercel (deployment)
- Stripe (payments)
- OpenClaw (automation)

## Disclaimer
For informational purposes only. Not financial advice. Trading involves risk.
