"""Summarise a kicad-cli DRC json: counts, then every non-silk violation and unconnected item."""
import json, sys, collections
d = json.load(open(sys.argv[1]))
skip = set(sys.argv[2:])  # e.g. silk_overlap silk_over_copper
print("violations:", dict(collections.Counter(v["type"] for v in d["violations"])))
print("unconnected:", len(d["unconnected_items"]))
for v in d["violations"]:
    if v["type"] in skip: continue
    p = v["items"][0]["pos"]
    print(f'- {v["type"]}: {v["description"][:70]} @ ({p["x"]:.2f},{p["y"]:.2f}) | ' + "; ".join(i["description"] for i in v["items"]))
for u in d["unconnected_items"]:
    print("U:", "; ".join(i["description"] for i in u["items"]))
