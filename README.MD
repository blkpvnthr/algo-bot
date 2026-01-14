
# 📡 algo-bot

A real-time trading assistant built with Flask and Python that connects to the Alpaca Markets API to execute live trades, respond to price movements, and receive TradingView alerts via webhooks.

---

![Welcome!](images/algobot2.png)

## Usage

### Prerequisites
Open a terminal create a new virtual environment then install dependencies.
```bash
pip install -r requirements.txt
```

### ⚙️ To Get Started
Run `tv-alpaca.py` to connect to realtime market data. Trade logic should be written within `tv-alpaca.py`.
```bash
python tv-alpaca.py
```

### `Place a trade`
To execute a trade manually, send a POST request to the `/trade` endpoint with the following parameters:

```bash
curl -X POST http://localhost:5000/trade -d "symbol=AAPL&qty=1&side=buy"
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
├── tv-alpaca.py         # Flask + Alpaca integration
├── templates/           # HTML templates (index, response, webhook)
├── static/              # Optional for CSS/JS
├── requirements.txt     # Dependencies
```

---

## 🔒 Security Note
Do **NOT** commit your Alpaca API credentials. Use environment variables or a secrets manager in production.


---

## 🧠 Author

This project was built by **[Asmaa Abdul-Amin](https://asmaa.dev)**. 
🔗 [Portfolio](https://asmaa.dev)  
🐙 [GitHub](https://github.com/blkpvnthr)  
💼 [LinkedIn](https://linkedin.com/in/blkpvnthr)


---

> ⚠️ This project is for educational use only. It does not constitute financial advice or real trading recommendations.
