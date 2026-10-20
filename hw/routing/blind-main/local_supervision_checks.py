"""Inspect actual local control copper and the encoder regulator return topology."""
from pathlib import Path
import json
import math
import pcbnew

HERE = Path(__file__).resolve().parent


def encoder_star(b, m):
    parts = m.parts(b)
    pin = next(p for p in parts["encoder.ic"].Pads() if p.GetNumber() == "2")
    land = pcbnew.SHAPE_POLY_SET()
    pin.TransformShapeToPolygon(land, pcbnew.F_Cu, 0, 500, pcbnew.ERROR_INSIDE)
    star = next(g for g in m.copper_components(b, "lv", include_planes=False)
                if ("pad", "encoder.ic", "2") in [x[:3] for x in g])
    routes = {x[1] for x in star if x[0] == "route"}
    ends = {x[1:3] for x in star if x[0] == "pad"}
    assert ends == {("encoder.ic", "2"), ("encoder.c_input", "2"),
                    ("encoder.c_output", "2")}, ("Encoder ground star mixed", ends)
    vias = {t.m_Uuid.AsString() for t in b.GetTracks()
            if isinstance(t, pcbnew.PCB_VIA)}
    assert len(routes & vias) == 1, "Encoder ground must have one plane entry"
    items = [(("pad", a, n), p) for a, n in ends for p in parts[a].Pads()
             if p.GetNumber() == n]
    items += [(("route", t.m_Uuid.AsString()), t) for t in b.GetTracks()
              if t.m_Uuid.AsString() in routes and
              (isinstance(t, pcbnew.PCB_VIA) or t.GetLayer() == pcbnew.F_Cu)]
    nodes = []
    for key, item in items:
        shape = pcbnew.SHAPE_POLY_SET()
        item.TransformShapeToPolygon(shape, pcbnew.F_Cu, 0, 500, pcbnew.ERROR_OUTSIDE)
        shape.BooleanSubtract(land)
        for i in range(shape.OutlineCount()):
            piece = pcbnew.SHAPE_POLY_SET(); piece.NewOutline()
            outline = shape.COutline(i)
            for j in range(outline.PointCount()):
                piece.Append(outline.CPoint(j))
            if piece.Area() > 1:
                nodes.append((key, piece))
    parent = list(range(len(nodes)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i

    for i, (_, a) in enumerate(nodes):
        for j, (_, c) in enumerate(nodes[:i]):
            if a.Collide(c, 0):
                parent[find(i)] = find(j)
    membership = {}
    for address in ("encoder.c_input", "encoder.c_output"):
        found = {find(i) for i, (key, _) in enumerate(nodes)
                 if key == ("pad", address, "2")}
        assert len(found) == 1, (address, found)
        membership[address] = next(iter(found))
    assert len(set(membership.values())) == 2, \
        "Encoder capacitor ground branches join outside IC GND land"
    return {"pads": sorted([list(x) for x in ends]), "plane_vias": 1,
            "capacitor_ground_components_after_removing_ic_land": 2,
            "scope": "Actual front copper; saved plane excluded"}


def verify(b, m):
    data = json.loads((HERE / "local-supervision-routes.json").read_text())
    parts = m.parts(b)
    groups = {}
    branches = []
    for r in data["routes"]:
        a, n = r["start"]; c, k = r["end"]; n = str(n); k = str(k)
        net = r["net"]
        for address, number in ((a, n), (c, k)):
            pads = [p for p in parts[address].Pads() if p.GetNumber() == number]
            assert pads and all(p.GetNetname() == net for p in pads), \
                ("Local endpoint/net changed", address, number, net)
        if net not in groups:
            groups[net] = m.copper_components(b, net)
        if (a, n) == (c, k):
            assert any(("pad", a, n) in [x[:3] for x in g] and
                       any(x[0] == "zone" for x in g) for g in groups[net]), \
                ("Local ground open", a, n)
        else:
            assert any(all(
                sum(x[:3] == ("pad", address, number) for x in g) ==
                sum(p.GetNumber() == number for p in parts[address].Pads())
                for address, number in ((a, n), (c, k))) for g in groups[net]), \
                ("Local branch open", a, n, c, k)
        branches.append({"start": [a, n], "end": [c, k], "net": net,
                         "recipe_length_mm": sum(math.dist(x[:2], y[:2])
                             for x, y in zip(r["path"], r["path"][1:])),
                         "layers": sorted({x[2] for x in r["path"]})})
    return {"connected_branches": branches, "encoder_ground_star": encoder_star(b, m),
            "limits": ["Onward MCU and ADC connections remain incomplete",
                       "Recipe lengths do not establish analog performance",
                       "No physical timing, noise or thermal qualification"]}
