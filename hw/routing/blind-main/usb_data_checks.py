"""USB connectivity, saved return geometry and actual centerline path audit."""
from pathlib import Path
import collections, heapq, json, math
import pcbnew

LAYERS = (pcbnew.F_Cu, pcbnew.B_Cu)


def poly(item, layer):
    result = pcbnew.SHAPE_POLY_SET()
    item.TransformShapeToPolygon(result, layer, 0, 500, pcbnew.ERROR_OUTSIDE)
    return result


def plane(b, layer):
    result = pcbnew.SHAPE_POLY_SET()
    for z in b.Zones():
        if not z.GetIsRuleArea() and z.GetLayer() == layer and z.GetNetname() == "lv":
            result.BooleanAdd(z.GetFilledPolysList(layer))
    return result


def paths(b, parts, net, contacts, esd_pin, resistor):
    """Split actual track centerlines at coincident junctions, then shortest paths."""
    tracks = [t for t in b.GetTracks() if t.GetNetname() == net]
    segments = [t for t in tracks if not isinstance(t, pcbnew.PCB_VIA)]
    vias = [t for t in tracks if isinstance(t, pcbnew.PCB_VIA)]
    def key(p, layer):
        return (p.x, p.y, layer)
    nodes = set()
    for t in segments:
        nodes.add(key(t.GetStart(), t.GetLayer()))
        nodes.add(key(t.GetEnd(), t.GetLayer()))
    for v in vias:
        for layer in LAYERS:
            nodes.add(key(v.GetPosition(), layer))
    def pad(a, n):
        return next(p for p in parts[a].Pads() if p.GetNumber() == str(n))
    starts = {n: key(pad("usb.connector", n).GetPosition(), pcbnew.F_Cu)
              for n in contacts}
    goal = key(pad(resistor, 2).GetPosition(), pcbnew.F_Cu)
    protection = key(pad("controller.usb_esd", esd_pin).GetPosition(), pcbnew.F_Cu)
    nodes.update(starts.values()); nodes.update((goal, protection))
    edges = collections.defaultdict(dict)
    for t in segments:
        a, c = t.GetStart(), t.GetEnd()
        dx, dy = c.x-a.x, c.y-a.y
        norm2 = dx*dx+dy*dy
        assert norm2 > 0
        on = []
        for n in nodes:
            if n[2] != t.GetLayer():
                continue
            ratio = ((n[0]-a.x)*dx+(n[1]-a.y)*dy)/norm2
            distance = abs((n[0]-a.x)*dy-(n[1]-a.y)*dx)/math.sqrt(norm2)
            if -.00000001 <= ratio <= 1.00000001 and distance <= 1.01:
                on.append((ratio, n))
        on.sort()
        for (_, p), (_, q) in zip(on, on[1:]):
            length = math.dist(p[:2], q[:2])/1e6
            edges[p][q] = (length, 0); edges[q][p] = (length, 0)
    for v in vias:
        p, q = [key(v.GetPosition(), layer) for layer in LAYERS]
        edges[p][q] = (0, 1); edges[q][p] = (0, 1)
    result = {}
    for contact, start in starts.items():
        # A longer parallel bypass must also fail. Checking only the shortest
        # path would miss a protection connection that became a side branch.
        reached = {start}
        pending = [start]
        while pending:
            p = pending.pop()
            for q in edges[p]:
                if q != protection and q not in reached:
                    reached.add(q)
                    pending.append(q)
        assert goal not in reached, ("Trace path bypasses ESD pad", contact)
        queue = [(0., 0, start)]
        best = {start: (0., 0)}
        parent = {}
        while queue:
            distance, transitions, p = heapq.heappop(queue)
            if (distance, transitions) != best[p]:
                continue
            if p == goal:
                break
            for q, (length, crossed) in edges[p].items():
                candidate = (distance+length, transitions+crossed)
                if candidate < best.get(q, (float("inf"), 999)):
                    best[q] = candidate; parent[q] = p
                    heapq.heappush(queue, (*candidate, q))
        assert goal in best, ("No actual centerline path", contact)
        route = [goal]
        while route[-1] != start:
            route.append(parent[route[-1]])
        assert protection in route, ("Protection is a branch, not on through path", contact)
        result[contact] = {"planar_mm": best[goal][0],
                           "active_layer_transitions": best[goal][1]}
    return result


def verify(b, m):
    parts = m.parts(b)
    returns = {z.GetZoneName(): z for z in b.Zones() if not z.GetIsRuleArea()}
    assert set(returns) == {"TRIAL_IN1_GND_RETURN", "USB_LOCAL_IN2_RETURN"}
    assert returns["TRIAL_IN1_GND_RETURN"].GetLayer() == pcbnew.In1_Cu
    assert returns["USB_LOCAL_IN2_RETURN"].GetLayer() == pcbnew.In2_Cu
    assert all(z.GetNetname() == "lv" for z in returns.values())
    def pad(a, n):
        return next(p for p in parts[a].Pads() if p.GetNumber() == str(n))
    fronts = plane(b, pcbnew.In1_Cu)
    backs = plane(b, pcbnew.In2_Cu)
    all_paths = {}
    reference = {}
    for suffix, contacts, pin, resistor in [
            ("dp", ("A6", "B6"), 3, "controller.r_dp"),
            ("dm", ("A7", "B7"), 5, "controller.r_dm")]:
        net = pad("usb.connector", contacts[0]).GetNetname()
        assert net == "usb_"+suffix
        groups = m.copper_components(b, net)
        required = {("usb.connector", n) for n in contacts}
        required |= {("controller.usb_esd", str(pin)), (resistor, "2")}
        assert len(groups) == 1
        assert required <= {k[1:3] for k in groups[0] if k[0] == "pad"}
        all_paths[suffix] = paths(b, parts, net, contacts, pin, resistor)
        vias = [v for v in b.GetTracks() if isinstance(v, pcbnew.PCB_VIA)
                and v.GetNetname() == net]
        assert len(vias) == (0 if suffix == "dp" else 3)
        for v in vias:
            for layer, fill in [(pcbnew.In1_Cu, fronts), (pcbnew.In2_Cu, backs)]:
                overlap = poly(v, layer); overlap.BooleanIntersection(fill)
                assert overlap.Area() < 1, "Saved ground fill overlaps USB signal via"
        by_layer = {}
        for layer, fill in [(pcbnew.F_Cu, fronts), (pcbnew.B_Cu, backs)]:
            footprint = pcbnew.SHAPE_POLY_SET()
            for t in b.GetTracks():
                if not isinstance(t, pcbnew.PCB_VIA) and t.GetNetname() == net and t.GetLayer() == layer:
                    footprint.BooleanAdd(poly(t, layer))
            footprint.BooleanSubtract(fill)
            uncovered = footprint.Area()/1e12
            # Only D-minus changes layers. Its own small antipad openings are
            # necessary; no other trace-footprint reference gap is accepted.
            for v in vias:
                opening = pcbnew.PCB_VIA(b)
                opening.SetPosition(v.GetPosition())
                reference_layer = pcbnew.In1_Cu if layer == pcbnew.F_Cu else pcbnew.In2_Cu
                clearance = max(z.GetLocalClearance() for z in b.Zones()
                                if not z.GetIsRuleArea() and z.GetLayer() == reference_layer
                                and z.GetNetname() == "lv")
                assert 150000 <= clearance <= 200000
                arc_error = b.GetDesignSettings().m_MaxError
                assert 0 < arc_error <= 5000
                opening.SetWidth(v.GetWidth(reference_layer)+2*(clearance+arc_error+500))
                footprint.BooleanSubtract(poly(opening, layer))
            assert footprint.Area() < 1, ("Unexpected USB reference gap", suffix, layer)
            by_layer[pcbnew.LayerName(layer)] = uncovered
        reference[suffix] = by_layer
    ground = m.copper_components(b, "lv", include_planes=False)
    esd = next(g for g in ground if any(k[:3] == ("pad", "controller.usb_esd", "4") for k in g))
    assert {k[1:3] for k in esd if k[0] == "pad"} == {
        ("controller.usb_esd", str(n)) for n in (1, 2, 4)}
    via_ids = {v.m_Uuid.AsString() for v in b.GetTracks() if isinstance(v, pcbnew.PCB_VIA)}
    assert sum(k[0] == "route" and k[1] in via_ids for k in esd) == 1
    assert all(x["active_layer_transitions"] == 0 for x in all_paths["dp"].values())
    assert all(x["active_layer_transitions"] == 2 for x in all_paths["dm"].values())
    return {"connected_data_nets": 2, "paths": all_paths,
            "unreferenced_trace_union_mm2": reference,
            "esd_ground_plane_entries": 1,
            "own_antipad_radius_tolerance_mm": (b.GetDesignSettings().m_MaxError+500)/1e6,
            "scope": "Actual planar centerlines and direct trace footprint only. D-minus has two additional barrel transitions. No electrical-delay, field-spread, ESD-current or 90-ohm impedance qualification."}
