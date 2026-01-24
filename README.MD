
# 💰 algo-bot

A real-time trading assistant built with Flask and Python that connects to the Alpaca Markets API to execute live trades, respond to price movements, and receive TradingView alerts via webhooks.

---

![Welcome!](images/algobot2.png)

## Usage

### Prerequisites
Open a terminal and create a new virtual environment then install dependencies.
```bash
pip install -r requirements.txt
```

### ⚙️ To Get Started
Run `app.py` to connect to realtime market data.
```bash
python app.py
```

### Open the App
Open the browser and navigate to `http://localhost:5002`.
```bash
http://localhost:5002
```

### `Place a trade`
To execute a trade manually, send a POST request to the `/trade` endpoint with the following parameters:

```bash
curl -X POST http://localhost:5002/trade -d "symbol=AAPL&qty=1&side=buy"
```

---

## 🚀 Features

- 🔄 **Real-Time Data via WebSocket** (Alpaca IEX)
- 🛒 **Market Order Execution** via Alpaca Trading API
- 🧠 **Trade Triggers Based on Price Movement**
- 📤 **Webhook Endpoint for TradingView Alerts**
- 🧵 **Multithreaded WebSocket Handling**
- 📋 **JSON-Formatted Order Logs for Easy Auditing**

---

## 🧱 Tech Stack

| Tool         | Purpose                             |
|--------------|-------------------------------------|
| Python       | Core programming language           |
| Flask        | Web server and API routing          |
| Alpaca API   | Trading and market data             |
| WebSocketApp | Real-time data stream               |
| HTML/Jinja2  | Frontend rendering (basic)          |
| threading    | Concurrent WebSocket execution      |


---

## 📂 Project Structure

```
algo-bot/
├── app.py                  # Flask app factory + route registration
├── wsgi.py                 # Gunicorn entrypoint (app = create_app())
│
├── api/                    # REST API blueprints
│   ├── __init__.py
│   ├── runs.py             # /api/runs (backtests, execution)
│   ├── strategies.py       # /api/strategies (saved scripts)
│   └── schemas.py          # Request/response validation
│
├── models/                 # Persistence layer (SQLite)
│   ├── __init__.py
│   ├── db.py               # DB init + connection helpers
│   ├── run_repo.py         # Runs table access
│   └── strategy_repo.py    # Strategies table access
│
├── services/               # Core business logic
│   ├── __init__.py
│   ├── data_sources.py     # Alpaca / yfinance loaders
│   ├── runner_service.py   # Run orchestration (local/Docker)
│   ├── artifact_service.py # Artifact discovery
│   ├── storage_service.py  # Workspace + file management
│   └── limits.py           # Safety limits (timeouts, sizes)
│
├── web/
│   ├── templates/          # Jinja templates (UI)
│   │   ├── index.html      # Dashboard
│   │   ├── brokers.html    # Broker cards page
│   │   ├── scripts.html    # Online IDE / backtester
│   │   └── navbar.html
│   │
│   └── static/             # CSS / JS assets
│       ├── styles.css
│       └── scripts.js
│
├── data/                   # Local SQLite DB + cached data
│   └── app.db
│
├── workspaces/             # Per-run execution sandboxes
│   └── <run_id>/
│       ├── data/
│       ├── artifacts/
│       └── run.json
│
├── tests/                  # pytest tests
│   └── test_smoke.py
│
├── requirements.txt        # Python dependencies
├── .github/
│   └── workflows/
│       ├── ci.yml          # Lint + tests + app startup
│       └── pages.yml       # Static export + GitHub Pages deploy
│
└── README.md

```

---

## 🔒 Security Note
Do **NOT** commit your Alpaca API credentials. Use environment variables or a secrets manager in production.


---

## 🧠 Author

This project was built by **[Asmaa Abdul-Amin](https://asmaa.dev)**.

> ⚠️ This project is for educational use only. It does not constitute financial advice or real trading recommendations.
