#!/usr/bin/env python3
"""Read public JLC part pages and retain only sourcing evidence, never account data.

This is a candidate shortlist, not a manufacturing BOM or a purchasing action.
JLC's public server data format can change; a failed extraction must stay visible.
"""
import concurrent.futures
import datetime
import html
import json
from pathlib import Path
import re
import urllib.request

PARTS = [
    ("BQ24133RGYR", "C44478"),
    ("BQ25792RQMR", "C2862876"),
    ("BQ25798RQMR", "C2876593"),
    ("BQ40Z50RSMR-R2", "C2845123"),
    ("DRV8874PWPR", "C1855818"),
    ("ESP32-C6-MINI-1-N4", "C5736265"),
    ("ESP32-C6-MINI-1-H4", "C6553337"),
    ("ESP32-C6-WROOM-1-N4", "C6034714"),
    ("TPS62902RPJR", "C2870154"),
    ("TPS62177DQCR", "C91241"),
    ("BQ76942PFBR", "C2692351"),
    ("MAX17320G20+", "C7457894"),
    ("MAX17320G22+", "C2914309"),
    ("BH-21700-A5BJ001", "C20606809"),
    ("BH-21700-B1BJ001", "C20606791"),
]
FIELDS = (
    "componentModelEn", "componentLibraryType", "preferredComponentFlag",
    "assemblyMode", "stockCount", "overseasStockCount", "canPresaleNumber",
    "preMinPurchaseNum", "leastPatchNumber", "lossNumber", "noBuyReason",
    "initialPrice", "assemblyComponentFlag", "xrayFlag", "componentProductType",
    "fixtureFlag", "specialComponentFee",
)


def fetch(pair):
    mpn, code = pair
    url = f"https://jlcpcb.com/partdetail/{mpn}/{code}"
    result = {"mpn": mpn, "lcsc": code, "url": url,
              "observed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
              "currency": "USD"}
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            source = response.read().decode()
        chunks = "".join(json.loads(m)[1] for m in re.findall(
            r"self\.__next_f\.push\((\[1,.*?\])\)</script>", source))
        objects = []

        def walk(value):
            if isinstance(value, dict):
                if value.get("componentCode") == code:
                    objects.append(value)
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)

        for line in chunks.splitlines():
            try:
                walk(json.loads(line.split(":", 1)[1]))
            except (ValueError, IndexError):
                continue
        metadata, prices = {}, {}
        for obj in objects:
            for key in FIELDS:
                if key in obj and obj[key] != "$undefined":
                    metadata[key] = obj[key]
            if "productPrice" in obj:
                price = {key: obj[key] for key in ("startNumber", "endNumber", "productPrice")}
                prices[price["startNumber"]] = price
        # The page can contain scripts before product content, so also inspect
        # the HTML with script blocks removed. Do not infer eligibility from IDs.
        visible = html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<script.*?</script>", "", source, flags=re.S)))
        visible = " ".join(visible.split())
        match = re.search(r"PCBA Type\s+(Economic and Standard|Standard Only)", visible)
        result.update(metadata=metadata, price_breaks=[prices[k] for k in sorted(prices)],
                      pcba_type=match.group(1) if match else "not exposed in page",
                      stock_note="overseasStockCount is not in-house SMT stock. preMinPurchaseNum is unverified internal metadata, not a confirmed MOQ. Final BOM matching and quote still required")
        if not metadata or not prices:
            result["error"] = "Incomplete public page extraction; do not treat as confirmed sourcing"
        elif metadata.get("componentModelEn") != mpn:
            result["error"] = "Part-number mismatch: requested " + mpn + ", page says " + str(metadata.get("componentModelEn"))
    except Exception as error:
        result["error"] = f"{type(error).__name__}: {error}"
    return result


if __name__ == "__main__":
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        parts = list(pool.map(fetch, PARTS))
    result = {
        "schema": 1,
        "status": "candidate-parts-not-orderable-bom",
        "note": "Live public JLC page metadata. Prices exclude attrition, setup, tax and shipping. No stock reserved. Revalidate at quote.",
        "parts": parts,
    }
    target = Path(__file__).with_name("electronics-sourcing-snapshot.json")
    target.write_text(json.dumps(result, indent=2) + "\n")
    for part in parts:
        print(part["mpn"], part.get("pcba_type"), part.get("metadata", {}).get("overseasStockCount"), part.get("error", ""))
