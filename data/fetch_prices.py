"""Fetch a daily close series for Day 8. Run this on a machine with network access.

Day 8 shipped with AAPL because the environment it was built in blocks market-data
hosts at the proxy (stooq returns 403, Yahoo is unreachable). AAPL was the only
real daily equity series available from a public GitHub dataset.

SPY is the better series and this fetches it:

  - it is an index, so the return distribution is not dominated by one company's
    idiosyncratic news
  - a decade gives about 120 independent months instead of AAPL's 24
  - it matches the underlying used in the vol-surface project, so the two repos
    describe the same instrument

Usage:
    python data/fetch_prices.py                 # SPY, 10 years, -> data/spy_daily.csv
    python data/fetch_prices.py QQQ 5           # any ticker, any number of years

Then point Day 8 at it:
    CSV_PATH, CLOSE_COL = "data/spy_daily.csv", "Close"

Sources are tried in order; the first that works wins. stooq needs no key and no
package, so it is first.
"""

import csv
import io
import sys
import urllib.request


def from_stooq(ticker, years):
    """Stooq serves daily OHLC as plain CSV with no key and no dependencies."""
    url = f"https://stooq.com/q/d/l/?s={ticker.lower()}.us&i=d"
    with urllib.request.urlopen(url, timeout=30) as r:
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


def main():
    ticker = sys.argv[1] if len(sys.argv) > 1 else "SPY"
    years = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    out = f"data/{ticker.lower()}_daily.csv"

    last_error = None
    for source in (from_stooq, from_yfinance):
        try:
            rows = source(ticker, years)
        except Exception as exc:                      # noqa: BLE001 - report and try next
            print(f"  {source.__name__}: {type(exc).__name__}: {exc}")
            last_error = exc
            continue

        with open(out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["Date", "Close"])
            w.writeheader()
            w.writerows(rows)
        print(f"wrote {out}: {len(rows)} rows, {rows[0]['Date']} -> {rows[-1]['Date']}")
        print(f"\nNow edit day8_real_paths.py:")
        print(f'    CSV_PATH, CLOSE_COL = "{out}", "Close"')
        print("and rerun it. Nothing else changes -- the engine takes any path array.")
        return 0

    print(f"\nAll sources failed. Last error: {last_error}")
    print("If you are behind a restrictive proxy, export the series from your")
    print("broker or any charting tool as CSV with Date and Close columns.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
