# market-prices

Public EUR prices for a short list of ETFs, shares and crypto, refreshed by a GitHub Action
(weekdays at 09:30, 13:30 and 17:35 Madrid time; nothing at weekends). Holds no positions, quantities or account data.

- `instruments.json` — the list of ISINs and crypto symbols to price. Add a line to track a new one.
- `prices.json` / `prices.js` — latest prices (`window.MARKET_PRICES`). Each update is also published to npm as
  `amozz10-market-prices` and served at `https://cdn.jsdelivr.net/npm/amozz10-market-prices@1/prices.js`
  (fallback `https://unpkg.com/amozz10-market-prices@1/prices.js`).
- Sources: onvista (securities, Xetra EUR quote preferred) and Coinbase spot prices (crypto).
  A failed lookup keeps the last good price; moves above 25% are rejected.

Publishing uses npm trusted publishing for `.github/workflows/prices.yml` (configured on npmjs.com, no token).

Run it by hand from the Actions tab → "Update prices" → Run workflow.
