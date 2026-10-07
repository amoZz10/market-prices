"""Fetch EUR prices for the instruments in instruments.json and write prices.json + prices.js.

Sources (public, no key): onvista (securities by ISIN, prefers the Xetra EUR quote)
and Coinbase spot prices (crypto). A failed lookup keeps the previous price.
"""
import json, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OV = "https://api.onvista.de/api/v1/"
KINDS = {"FUND": "funds", "STOCK": "stocks", "BOND": "bonds", "CERTIFICATE": "certificates", "INDEX": "indices"}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "market-prices/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


def onvista(isin):
    paths = []
    try:
        hits = get(OV + "instruments/query?searchValue=" + isin).get("list", [])
        hit = next((h for h in hits if h.get("isin") == isin), hits[0] if hits else None)
        if hit and hit.get("entityType") in KINDS:
            paths.append(KINDS[hit["entityType"]])
    except Exception:
        pass
    for p in paths or ["funds", "stocks"]:
        try:
            d = get(f"{OV}{p}/ISIN:{isin}/snapshot")
        except Exception:
            continue
        qs = [d.get("quote")] + (d.get("quoteList") or {}).get("list", [])
        qs = [q for q in qs if q and q.get("isoCurrency") == "EUR" and (q.get("last") or 0) > 0 and q.get("datetimeLast")]
        if not qs:
            continue
        newest = max(q["datetimeLast"][:10] for q in qs)
        same_day = [q for q in qs if q["datetimeLast"][:10] == newest]
        q = (next((q for q in same_day if (q.get("market") or {}).get("codeExchange") == "GER"), None)
             or max(same_day, key=lambda q: q["datetimeLast"]))
        name = (d.get("instrument") or {}).get("name")
        return {"price": q["last"], "date": q["datetimeLast"][:10], "at": q["datetimeLast"], "currency": "EUR",
                "source": "onvista · " + ((q.get("market") or {}).get("name") or "exchange"), "name": name}
    raise RuntimeError("no EUR quote")


def coinbase(sym):
    d = get(f"https://api.coinbase.com/v2/prices/{sym.upper()}-EUR/spot")
    px = float(d["data"]["amount"])
    now = datetime.now(timezone.utc)
    return {"price": px, "date": now.date().isoformat(), "at": now.isoformat(timespec="seconds"), "currency": "EUR",
            "source": "Coinbase spot price"}


def main():
    cfg = json.loads((ROOT / "instruments.json").read_text())
    old_path = ROOT / "prices.json"
    old = json.loads(old_path.read_text()).get("quotes", {}) if old_path.exists() else {}
    quotes, errors = dict(old), []
    jobs = [(i, onvista) for i in cfg.get("securities", [])] + [(c.lower(), lambda s: coinbase(s)) for c in cfg.get("crypto", [])]
    for key, fn in jobs:
        try:
            q = fn(key)
            prev = (old.get(key) or {}).get("price")
            if prev and abs(q["price"] / prev - 1) > 0.25:
                errors.append(f"{key}: {q['price']} rejected, more than 25% from {prev}")
                continue
            quotes[key] = q
        except Exception as e:
            errors.append(f"{key}: {e}")
    wanted = set(cfg.get("securities", [])) | {c.lower() for c in cfg.get("crypto", [])}
    quotes = {k: v for k, v in sorted(quotes.items()) if k in wanted}
    doc = {"fetchedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "quotes": quotes, "errors": errors}
    old_path.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    (ROOT / "prices.js").write_text("window.MARKET_PRICES=" + json.dumps(doc, ensure_ascii=False) + ";\n")
    print(f"{len(quotes)} quotes, {len(errors)} errors")
    for e in errors:
        print("  ", e)
    return 0 if quotes else 1


if __name__ == "__main__":
    sys.exit(main())
