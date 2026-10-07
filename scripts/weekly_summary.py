"""Weekly net-worth email for the Wealth Ledger dashboard.

Reads the dashboard's own summary (digest/latest.json) and saved history (snapshots/*.json)
from a folder, reprices listed holdings with this repository's public price list, accrues
deposit interest, and prints a short message. Holds no personal data itself.

Usage: python weekly_summary.py <folder>
Writes <folder>/new_snapshot_<date>.json when that day has no saved point yet.
"""
import json, os, sys, time, urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

DASHBOARD = "https://claude.ai/artifact/7r1hr4hwqc3VkNt2YkCh1w"
PRICE_URLS = ["https://unpkg.com/amozz10-market-prices@1/prices.json",
              "https://cdn.jsdelivr.net/npm/amozz10-market-prices@1/prices.json"]
DIAS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def load(p):
    d = json.loads(Path(p).read_text())
    return d.get("data", d) if isinstance(d, dict) and "data" in d and "version" in d else d


def eur(v, sign=False):
    s = f"{abs(v):,.0f}".replace(",", ".")
    pre = ("+" if v > 0 else "−" if v < 0 else "±") if sign else ("−" if v < 0 else "")
    return f"{pre}{s} €"


def fdate(iso):
    d = date.fromisoformat(iso)
    return f"{DIAS[d.weekday()]} {d.day} {MESES[d.month - 1]}"


def prices():
    best = {}
    for u in PRICE_URLS:
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "weekly-summary"}), timeout=20) as r:
                d = json.load(r)
            if str(d.get("fetchedAt", "")) > str(best.get("fetchedAt", "")):
                best = d
        except Exception:
            continue
    return best.get("quotes", {})


def main(folder):
    folder = Path(folder)
    dg = load(next(folder.rglob("digest/latest.json")))
    snaps = sorted((load(p) for p in folder.rglob("snapshots/*.json")), key=lambda s: s["date"])
    now = datetime.now(ZoneInfo("Europe/Madrid"))
    if now.weekday() == 5 and now.hour < 6:  # a late start just after midnight still reports Friday
        now -= timedelta(days=1)
    T = os.environ.get("WS_TODAY") or now.date().isoformat()  # WS_TODAY only for testing

    q = prices()
    parts, px, delta_market = {}, {}, 0.0
    for a in dg["assets"]:
        v, rec = a["value"], a.get("rec") or {}
        if "px" in rec:
            nv = rec.get("cash", 0)
            for h in rec["px"]:
                p = (q.get(h["key"]) or {}).get("price") or h.get("price") or 0
                px[h["id"]] = p
                nv += h["qty"] * p
            v = round(nv, 2)
        elif rec.get("perDay"):
            end = min(T, rec.get("until") or T)
            days = max(0, (date.fromisoformat(end) - date.fromisoformat(dg["date"])).days)
            v = round(v + rec["perDay"] * days, 2)
        delta_market += v - a["value"]
        parts[a["id"]] = v
    total = round(sum(parts.values()), 2)
    gain = round((dg.get("gain") or 0) + delta_market, 2)
    names = {a["id"]: a["name"] for a in dg["assets"]}

    week_ago = (date.fromisoformat(T) - timedelta(days=7)).isoformat()
    prev = [s for s in snaps if s["date"] <= week_ago] or [s for s in snaps if s["date"] < T]
    prev = prev[-1] if prev else None

    out = [f"**Patrimonio: {eur(total)}**"]
    if prev:
        ch = round(total - prev["total"], 2)
        pc = ch / prev["total"] * 100 if prev["total"] else 0
        out[0] += f" · {eur(ch, True)} ({pc:+.1f} %) desde el {fdate(prev['date'])}"
        if prev.get("gain") is not None:
            ret = round(gain - prev["gain"], 2)
            out.append(f"Rentabilidad {eur(ret, True)} · Dinero que entra o sale {eur(ch - ret, True)}")
        ids = set(parts) | set(prev.get("parts", {}))
        rows = [(names.get(i, i), round(parts.get(i, 0) - prev["parts"].get(i, 0), 2)) for i in ids]
        rows = [r for r in rows if abs(r[1]) >= 0.5]
        rows.sort(key=lambda r: -abs(r[1]))
        if len(rows) > 6:
            rest = round(sum(r[1] for r in rows[6:]), 2)
            rows = rows[:6] + [("Resto", rest)]
        if rows:
            big = max(abs(r[1]) for r in rows) or 1
            out.append("")
            out.append("De dónde viene el cambio:")
            out.append("```")
            w = max(len(r[0]) for r in rows)
            for n, d in rows:
                bar = "█" * max(1, round(abs(d) / big * 14))
                out.append(f"{n:<{w}}  {eur(d, True):>9}  {'▲' if d > 0 else '▼'} {bar}")
            out.append("```")
    else:
        out.append("Primera semana con historial: la comparación empieza la próxima.")

    if dg["date"] < week_ago:
        out.append(f"\n_El panel no se abre desde el {fdate(dg['date'])}: los precios de mercado están al día, el resto viene de entonces._")

    rem, horizon = [], (date.fromisoformat(T) + timedelta(days=30)).isoformat()
    for r in sorted((r for r in dg.get("reminders", []) if r.get("d")), key=lambda r: r["d"]):
        if r["d"] <= horizon:
            days = (date.fromisoformat(r["d"]) - date.fromisoformat(T)).days
            when = "hoy" if days == 0 else (f"hace {-days} días" if days < 0 else f"en {days} días")
            rem.append(f"• {fdate(r['d'])} ({when}): {r['t']}")
    rem += [f"• {r['t']}" for r in dg.get("reminders", []) if not r.get("d") and not r.get("low")]
    out.append("\n**Recordatorios**")
    out += rem or ["• Nada pendiente esta semana."]
    out.append(f"\n[Abrir el panel]({DASHBOARD})")
    print("\n".join(out))

    if not any(s["date"] == T for s in snaps):
        snap = {"date": T, "total": total, "parts": parts, "gain": gain, "invested": dg.get("invested"),
                "px": px, "inv": {a["id"]: a["inv"] for a in dg["assets"] if a.get("inv") is not None},
                "ts": int(time.time() * 1000), "by": "weekly-summary"}
        (folder / f"new_snapshot_{T}.json").write_text(json.dumps(snap))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
