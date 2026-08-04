"""Fetch a daily close series for Day 8. Run this on a machine with network access.

Day 8 shipped with AAPL because the environment it was built in blocks
market-data hosts at the proxy (stooq returns 403, Yahoo is unreachable). AAPL
was the only real daily equity series available from a public GitHub dataset.

SPY is the better series and this fetches it:

  - it is an index, so the return distribution is not dominated by one company's
    idiosyncratic news
  - a decade gives about 120 independent months instead of AAPL's 24
  - it matches the underlying used in the vol-surface project, so the two repos
    describe the same instrument

Usage:
    python data/fetch_prices.py                 # SPY, 10 years -> data/spy_daily.csv
    python data/fetch_prices.py QQQ 5           # any ticker, any number of years

Then point Day 8 at it:
    CSV_PATH, CLOSE_COL = "data/spy_daily.csv", "Close"

Sources are tried in order; the first that works wins.
"""

import csv
import io
import ssl
import sys
import urllib.request


def _ssl_context():
    """Build an SSL context with a CA bundle Python can actually see.

    A stock python.org install on macOS does NOT use the system keychain, so
    HTTPS fails until you either run its Install Certificates.command or point
    it at certifi. Preferring certifi when it is present avoids that entirely.
    """
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def from_stooq(ticker, years):
    """Stooq serves daily OHLC as plain CSV -- no key, no packages."""
    url = f"https://stooq.com/q/d/l/?s={ticker.lower()}.us&i=d"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30, context=_ssl_context()) as r:
        rows = list(csv.DictReader(io.StringIO(r.read().decode())))
    if not rows or "Close" not in rows[0]:
        raise RuntimeError(f"stooq returned no usable data for {ticker}")
    return [{"Date": r["Date"], "Close": r["Close"]} for r in rows][-(years * 252):]


def from_yfinance(ticker, years):
    """Fallback. Requires `pip install yfinance`."""
    import yfinance as yf

    df = yf.download(ticker, period=f"{years}y", interval="1d",
                     auto_adjust=True, progress=False)
    if df.empty:
        raise RuntimeError(f"yfinance returned nothing for {ticker}")
    return [{"Date": str(d.date()), "Close": f"{float(c):.6f}"}
            for d, c in zip(df.index, df["Close"].to_numpy().ravel())]


SSL_HELP = """
An SSL verification error usually means one of two things.

1. Python cannot see any CA certificates. A python.org install on macOS ships
   without them wired up. Fix it with EITHER of:

       pip install certifi           # this script prefers certifi automatically
       open "/Applications/Python 3.14/Install Certificates.command"

   (adjust the version number to match your install)

2. Something on your network is intercepting TLS -- a school or corporate
   proxy, or some antivirus products. "self-signed certificate in certificate
   chain" points at this specifically. Options: run this from a different
   network, or install your organisation's root CA into certifi's bundle.

Do NOT work around this by disabling certificate verification. If neither fix
is available, export the series from your broker or any charting tool as a CSV
with Date and Close columns -- the analysis only needs those two.
"""


def main():
    ticker = sys.argv[1] if len(sys.argv) > 1 else "SPY"
    years = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    out = f"data/{ticker.lower()}_daily.csv"

    saw_ssl_error = False
    for source in (from_stooq, from_yfinance):
        try:
            rows = source(ticker, years)
        except Exception as exc:                      # noqa: BLE001 - report and try next
            if "CERTIFICATE_VERIFY_FAILED" in str(exc) or isinstance(exc, ssl.SSLError):
                saw_ssl_error = True
            print(f"  {source.__name__}: {type(exc).__name__}: {exc}")
            continue

        with open(out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["Date", "Close"])
            w.writeheader()
            w.writerows(rows)
        print(f"\nwrote {out}: {len(rows)} rows, {rows[0]['Date']} -> {rows[-1]['Date']}")
        print("\nNow edit day8_real_paths.py:")
        print(f'    CSV_PATH, CLOSE_COL = "{out}", "Close"')
        print("and rerun it. Nothing else changes -- the engine takes any path array.")
        return 0

    print("\nAll sources failed.")
    if saw_ssl_error:
        print(SSL_HELP)
    else:
        print("Export the series from your broker or any charting tool as a CSV")
        print("with Date and Close columns; the analysis only needs those two.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
