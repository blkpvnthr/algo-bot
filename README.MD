![Welcome!](images/welcome.png)


# Alpaca Trading Bot with WebSocket and Flask

This project implements a trading bot using Flask, the Alpaca API, and WebSockets to manage real-time market data and automate trades. The bot listens to trade, quote, and bar updates for specified symbols and executes market orders based on predefined criteria.

## Features
- **Market Order Execution**: Place buy/sell market orders through Alpaca’s API.
- **Real-time WebSocket Data**: Receive real-time trade, quote, and bar data for chosen symbols.
- **Webhook for TradingView**: Integrates with TradingView alerts via a webhook endpoint that allows trades to be places automatically.
- **Flask Interface**: Simple UI that allows you to place manual trades if needed.

## Requirements
- **Python** 3.7+
- **Flask**: `pip install flask`
- **Alpaca API**: Requires an Alpaca account with API keys.
- **websocket-client**: `pip install websocket-client`

## Setup

1. **Clone the Repository**:
    ```bash
    git clone https://github.com/your-username/your-repository.git
    cd your-repository
    ```

2. **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3. **Configure Alpaca API Keys**:
   Replace `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` with your Alpaca API credentials in the code.

4. **Run the Application**:
    ```bash
    python tv-alpaca.py
    ```
    This will start the Flask server on `http://0.0.0.0:5000`.

## Usage

- **/start**: Starts the WebSocket to receive real-time data updates.
- **/trade**: Manually trigger a market order.
- **/webhook**: Receives JSON data from TradingView alerts and triggers trades.
- **/**: Main page with options to start WebSocket and place manual trades.

## Code Structure

- `app.py`: Main application file. Handles Flask routes, WebSocket connection, and Alpaca API integration.
- `templates/`: Contains HTML templates for the Flask interface.

## Functions

- `place_market_order(symbol, qty, side)`: Submits a market order to Alpaca.
- `on_message(ws, message)`: Handles WebSocket messages and processes trade, quote, and bar updates.
- `on_open(ws)`: Authenticates and subscribes to symbols in the WebSocket connection.

## License
This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer
This bot is for educational purposes only. Use at your own risk; trading involves substantial risk.
# algo-bot
