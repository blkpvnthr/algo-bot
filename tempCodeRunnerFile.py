import json
from threading import Thread
from uuid import UUID
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for  # type: ignore
from websocket import WebSocketApp, enableTrace # type: ignore

from alpaca.trading.client import TradingClient # type: ignore
from alpaca.trading.enums import OrderSide, TimeInForce # type: ignore
from alpaca.trading.requests import MarketOrderRequest # type: ignore

app = Flask(__name__)

# Alpaca API credentials
ALPACA_API_KEY = 'your_alpaca_api_key'
ALPACA_SECRET_KEY = 'your_alpaca_secret_key'
BASE_URL = "https://paper-api.alpaca.markets/v2"
WS_URL = "wss://stream.data.alpaca.markets/v2/iex"

# Initialize the trading client
trading_client = TradingClient(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=True)

# Store previous prices for symbols
previous_prices = {}

# Function to serialize UUID and datetime objects
def json_serializer(obj):
    if isinstance(obj, UUID):
        return str(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

# Function to place a market order
def place_market_order(symbol, qty, side):
    order_data = MarketOrderRequest(
        symbol=symbol,
        qty=qty,
        side=OrderSide(side),
        time_in_force=TimeInForce.DAY
    )
    order_response = trading_client.submit_order(order_data=order_data)
    order_response_dict = order_response.__dict__
    print("Market order response:", json.dumps(order_response_dict, default=json_serializer, indent=4))
    return order_response_dict

# WebSocket message handler
def on_message(ws, message):
    data = json.loads(message)
    print("Received message:", json.dumps(data, indent=4))
    for update in data:
        if update['T'] == 't':  # Trade update
            trade_data = update
            symbol = trade_data['S']
            price = trade_data['p']
            print(f"Trade update for {symbol}: Price = {price}")
            if symbol == 'QBTS':
                if symbol in previous_prices:
                    previous_price = previous_prices[symbol]
                    if previous_price - price >= 0.05:
                        place_market_order(symbol="QBTS", qty=10, side="buy")
                previous_prices[symbol] = price

        elif update['T'] == 'q':  # Quote update
            quote_data = update
            symbol = quote_data['S']
            bid_price = quote_data['bp']
            ask_price = quote_data['ap']
            print(f"Quote update for {symbol}: Bid Price = {bid_price}, Ask Price = {ask_price}")

        elif update['T'] == 'b':  # Bar update
            bar_data = update
            symbol = bar_data['S']
            open_price = bar_data['o']
            high_price = bar_data['h']
            low_price = bar_data['l']
            close_price = bar_data['c']
            volume = bar_data['v']
            print(f"Bar update for {symbol}: Open = {open_price}, High = {high_price}, Low = {low_price}, Close = {close_price}, Volume = {volume}")

# WebSocket error handler
def on_error(ws, error):
    print("Error:", error)

# WebSocket close handler
def on_close(ws, close_status_code, close_msg):
    print("### closed ###")
    print(f"Status code: {close_status_code}, Reason: {close_msg}")

# WebSocket open handler
def on_open(ws):
    print("WebSocket opened")
    auth_data = {
        "action": "auth",
        "key": ALPACA_API_KEY,
        "secret": ALPACA_SECRET_KEY
    }
    ws.send(json.dumps(auth_data))
    subscribe_message = {
        "action": "subscribe",
        "trades": ["QBTS"],
        "quotes": ["QBTS"],
        "bars": ["QBTS"]
    }
    ws.send(json.dumps(subscribe_message))

@app.route('/start', methods=['POST'])
def start_websocket():
    def run_websocket():
        enableTrace(True)
        ws = WebSocketApp(
            WS_URL,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close
        )
        ws.run_forever()

    thread = Thread(target=run_websocket)
    thread.start()
    return render_template('response.html', response="WebSocket started")

@app.route('/trade', methods=['POST'])
def manual_trade():
    symbol = request.form['symbol']
    qty = request.form['qty']
    side = request.form['side']
    response = place_market_order(symbol, int(qty), side)
    return render_template('response.html', response=json.dumps(response, default=json_serializer, indent=4))

@app.route('/')
def index():
    return render_template('index.html')

# New route to handle TradingView webhooks and display response
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    print(f"Received webhook data: {data}")
    symbol = data.get('symbol')
    side = data.get('side')
    qty = data.get('qty', 1)  # Default to 1 if qty is not provided
    response = place_market_order(symbol, qty, side)
    response_json = json.dumps(response, default=json_serializer, indent=4)
    return render_template('webhooksss.html', response=response_json)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5001)
