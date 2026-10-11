# Signal Indicator (forex + crypto)

Pairs: EURUSD, GBPJPY, USDJPY, XAUUSD, BTCUSD, BNBUSD, ETHUSD

## Setup
1. Push this folder to a new GitHub repo.
2. Repo Settings > Pages > Deploy from branch > main > /docs.
3. Settings > Secrets > Actions > add NTFY_TOPIC (your secret topic name).
4. Actions tab > signals > Run workflow (it then runs every 15 min).
5. Phone: install ntfy app and subscribe to the same topic.
6. Open https://USERNAME.github.io/REPO/ in Chrome > menu > Add to Home screen.

Local run in Termux: pip install requests && python signals.py --loop
Not financial advice. Test on a demo account first.
