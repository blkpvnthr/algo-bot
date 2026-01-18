from __future__ import annotations

from models.db import get_conn
from dotenv import load_dotenv

load_dotenv()

import os
import time
import json
import requests
import threading
import itertools
import sys
import re
import xml.etree.ElementTree as ET
from decimal import Decimal
from datetime import datetime
from typing import List, Dict, Optional

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce


# ================= CONFIG =================

def _env_clean(s: Optional[str]) -> str:
    # Allows env like: POLL_SECONDS=900  # comment
    return (s or "").split("#")[0].strip()

POLL_SECONDS = int(_env_clean(os.getenv("POLL_SECONDS", "1800")))
MIN_TRADE_VALUE = Decimal(_env_clean(os.getenv("MIN_TRADE_VALUE_USD", "1000000")))
COPY_NOTIONAL = Decimal(_env_clean(os.getenv("COPY_TRADE_NOTIONAL_USD", "100")))

SEC_HEADERS = {
    "User-Agent": _env_clean(os.getenv("SEC_USER_AGENT", "insider-copytrade blkvpnthr@asmaa.dev")),
    "Accept-Encoding": "gzip, deflate",
}

EDGAR_FORM4_RSS = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4&count=100&output=rss"

# ==========================================


def require_env(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise RuntimeError(f"Missing env var: {name}")
    return val


def alpaca_client() -> TradingClient:
    return TradingClient(
        api_key=require_env("ALPACA_API_KEY"),
        secret_key=require_env("ALPACA_SECRET_KEY"),
        paper=_env_clean(os.getenv("ALPACA_PAPER", "true")).lower() in ("1", "true", "yes"),
    )


# ================= DB (shared with Flask) =====================

def init_worker_tables() -> None:
    """
    Ensure worker-specific tables exist in the shared Flask DB.
    (Your Flask init_db already creates insider_events; we ensure seen_form4 exists too.)
    """
    conn = get_conn()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS seen_form4 (
                accession TEXT PRIMARY KEY,
                first_seen INTEGER NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def seen(accession: str) -> bool:
    conn = get_conn()
    try:
        return (
            conn.execute("SELECT 1 FROM seen_form4 WHERE accession = ?", (accession,))
            .fetchone()
            is not None
        )
    finally:
        conn.close()


def mark_seen(accession: str) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO seen_form4(accession, first_seen) VALUES (?, ?)",
            (accession, int(time.time())),
        )
        conn.commit()
    finally:
        conn.close()


def emit_event(
    event_type: str,
    *,
    symbol: Optional[str] = None,
    value_usd: Optional[str] = None,
    accession: Optional[str] = None,
    cik: Optional[str] = None,
    payload: Optional[dict] = None,
) -> None:
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO insider_events(ts, event_type, symbol, value_usd, accession, cik, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(time.time()),
                event_type,
                symbol,
                value_usd,
                accession,
                cik,
                json.dumps(payload or {}),
            ),
        )
        conn.commit()
    finally:
        conn.close()


# ================= SEC helpers =====================

def fetch_current_form4_rss() -> List[Dict[str, str]]:
    """
    Returns a list of filings like:
      { "cik": "789019", "accession": "0000789019-26-000002", "acc_nodash": "000078901926000002" }
    """
    r = requests.get(EDGAR_FORM4_RSS, headers=SEC_HEADERS, timeout=30)
    r.raise_for_status()

    root = ET.fromstring(r.text)
    filings: List[Dict[str, str]] = []

    for item in root.findall(".//item"):
        link = (item.findtext("link") or "").strip()

        m = re.search(r"/Archives/edgar/data/(\d+)/(\d+)/(\d{10}-\d{2}-\d{6})-index\.html", link)
        if not m:
            continue

        filings.append(
            {"cik": m.group(1), "acc_nodash": m.group(2), "accession": m.group(3)}
        )

    return filings


def fetch_form4_xml_from_filing(cik_int: str, acc_nodash: str) -> str:
    """
    Use filing directory index.json to locate the best XML file in the filing folder,
    then download it.
    """
    index_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_nodash}/index.json"
    idx = requests.get(index_url, headers=SEC_HEADERS, timeout=30)
    idx.raise_for_status()

    items = idx.json().get("directory", {}).get("item", [])

    xml_candidates = [
        it for it in items
        if it.get("name", "").lower().endswith(".xml")
        and "xsl" not in it.get("name", "").lower()
    ]
    if not xml_candidates:
        raise RuntimeError(f"No XML found in filing directory: {index_url}")

    best = max(xml_candidates, key=lambda it: int(it.get("size", 0) or 0))
    xml_name = best["name"]

    xml_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_nodash}/{xml_name}"
    r = requests.get(xml_url, headers=SEC_HEADERS, timeout=30)
    r.raise_for_status()
    return r.text


def parse_form4(xml: str) -> Dict:
    """
    Parse a Form 4 XML.
    Returns:
      {
        "ticker": "AAPL",
        "buys":  [{"ticker": "AAPL", "value": Decimal(...), "code":"P"}],
        "sells": [{"ticker": "AAPL", "value": Decimal(...), "code":"S"}],
      }
    """
    root = ET.fromstring(xml)

    ticker = (
        (root.findtext(".//issuerTradingSymbol") or "")
        or (root.findtext(".//issuer/issuerTradingSymbol") or "")
    ).strip().upper()

    buys = []
    sells = []

    for txn in root.findall(".//nonDerivativeTransaction"):
        code = (txn.findtext("transactionCoding/transactionCode") or "").strip().upper()
        if code not in ("P", "S"):
            continue

        shares_txt = txn.findtext("transactionAmounts/transactionShares/value")
        price_txt = txn.findtext("transactionAmounts/transactionPricePerShare/value")
        if not shares_txt or not price_txt:
            continue

        shares = Decimal(shares_txt)
        price = Decimal(price_txt)
        value = shares * price

        entry = {"ticker": ticker, "value": value, "code": code}
        (buys if code == "P" else sells).append(entry)

    return {"ticker": ticker, "buys": buys, "sells": sells}


# ================= Trading =====================

def tradable(alpaca: TradingClient, symbol: str) -> bool:
    try:
        asset = alpaca.get_asset(symbol)
        return bool(asset.tradable) and asset.status == "active"
    except Exception:
        return False


def buy(alpaca: TradingClient, symbol: str) -> None:
    alpaca.submit_order(
        MarketOrderRequest(
            symbol=symbol,
            notional=float(COPY_NOTIONAL),
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY,
        )
    )
    print(f"[TRADE] BUY ${COPY_NOTIONAL} {symbol}")


def has_position(alpaca: TradingClient, symbol: str) -> bool:
    try:
        pos = alpaca.get_open_position(symbol)
        qty = Decimal(str(pos.qty))
        return qty != 0
    except Exception:
        return False


def liquidate(alpaca: TradingClient, symbol: str) -> None:
    alpaca.close_position(symbol)
    print(f"[LIQUIDATE] Closed position in {symbol}")


# ================= Spinner =====================

class Spinner:
    def __init__(self, message="Working"):
        self._spinner = itertools.cycle(["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"])
        self._stop = threading.Event()
        self.message = message
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        while not self._stop.is_set():
            sys.stdout.write(f"\r{next(self._spinner)} {self.message}")
            sys.stdout.flush()
            time.sleep(0.1)

    def start(self):
        self.thread.start()

    def stop(self, done_message="Idle / waiting for next poll"):
        self._stop.set()
        self.thread.join()
        sys.stdout.write("\r" + " " * (len(self.message) + 4) + "\r")
        print(f"✓ {done_message}")


# ================= Main =====================

def main():
    init_worker_tables()
    alpaca = alpaca_client()

    print("Running EDGAR Form 4 copy trader (GLOBAL)")

    while True:
        spinner = Spinner("Polling SEC EDGAR RSS (Form 4)…")
        spinner.start()

        cycle_new = 0
        cycle_errors = 0

        try:
            filings = fetch_current_form4_rss()

            for f in filings:
                accession = f["accession"]
                if seen(accession):
                    continue

                try:
                    xml = fetch_form4_xml_from_filing(f["cik"], f["acc_nodash"])
                    parsed = parse_form4(xml)
                    ticker = (parsed.get("ticker") or "").strip().upper() or None

                    print(f"\n[FORM4] {accession} CIK {f['cik']} ticker={ticker or 'UNKNOWN'}")
                    emit_event("FORM4_SEEN", symbol=ticker, accession=accession, cik=f["cik"])

                    # SELL -> liquidate if held (no threshold)
                    if ticker and parsed.get("sells"):
                        emit_event("SELL_SIGNAL", symbol=ticker, accession=accession, cik=f["cik"])
                        if has_position(alpaca, ticker):
                            print(f"[SIGNAL] Insider SELL for {ticker} — liquidating.")
                            liquidate(alpaca, ticker)
                            emit_event("LIQUIDATED", symbol=ticker, accession=accession, cik=f["cik"])

                    # BUY -> copy trade if >= threshold (place at most 1 buy per filing)
                    bought = False
                    for t in parsed.get("buys", []):
                        if bought:
                            break
                        if ticker and t["value"] >= MIN_TRADE_VALUE:
                            emit_event(
                                "BUY_SIGNAL",
                                symbol=ticker,
                                value_usd=str(t["value"]),
                                accession=accession,
                                cik=f["cik"],
                            )
                            if tradable(alpaca, ticker):
                                buy(alpaca, ticker)
                                emit_event(
                                    "BUY_PLACED",
                                    symbol=ticker,
                                    value_usd=str(COPY_NOTIONAL),
                                    accession=accession,
                                    cik=f["cik"],
                                )
                                bought = True

                    mark_seen(accession)
                    cycle_new += 1

                except Exception as e:
                    cycle_errors += 1
                    print(f"\n[ERROR] Filing {accession}: {e}")
                    emit_event("ERROR", accession=accession, cik=f.get("cik"), payload={"error": str(e)})

                time.sleep(1)  # SEC-friendly pacing

        except Exception as e:
            cycle_errors += 1
            print(f"\n[ERROR] RSS fetch/parse: {e}")
            emit_event("ERROR", payload={"error": f"rss_fetch_parse: {e}"})

        spinner.stop(done_message="Cycle complete — waiting for next poll")

        heartbeat_msg = {
            "new": cycle_new,
            "errors": cycle_errors,
            "next_poll_seconds": POLL_SECONDS,
        }

        print(
            f"[HEARTBEAT] {datetime.utcnow().isoformat()}Z — "
            f"new={cycle_new}, errors={cycle_errors}, next={POLL_SECONDS}s"
        )

        emit_event(
            "HEARTBEAT",
            payload=heartbeat_msg,
        )

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
# ================= END =====================