"""Replay finite USB paths on the freshly built clamp stage."""
from pathlib import Path
import json, shutil, sys
import pcbnew, wx
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from kicad_sexpr import parse, dumps, children, one
from generate_schematics import board_graph
from regen import signature


def point(uv):
    return pcbnew.VECTOR2I(round((100 + uv[0]) * 1e6),
                          round((175 - uv[1]) * 1e6))


def near(a, c):
    return max(abs(x - y) for x, y in zip(a, c)) < .000002


def main():
    app = wx.App(False)
    quiet = wx.LogNull()
    folder = ROOT / "work/main-route-build"
    source = folder / "regen.kicad_pcb"
    out = folder / "usb-data.kicad_pcb"
    data = json.loads((HERE / "usb-data-routes.json").read_text())
    source_bytes = source.read_bytes()
    tree = parse(source_bytes.decode())
    def uv(n, k):
        return [float(one(n, k)[1]) - 100, 175 - float(one(n, k)[2])]
    for row in data["removed_copper"]:
        candidates = [n for n in children(tree, row["kind"])
                      if one(n, "net")[1] == row["net"]]
        if row["kind"] == "segment":
            candidates = [n for n in candidates
                          if one(n, "layer")[1] == row["layer"]
                          and float(one(n, "width")[1]) == row["width_mm"]
                          and near(uv(n, "start"), row["uvs"][0])
                          and near(uv(n, "end"), row["uvs"][1])]
        else:
            candidates = [n for n in candidates
                          if near(uv(n, "at"), row["uv"])
                          and float(one(n, "size")[1]) == row["diameter_mm"]
                          and float(one(n, "drill")[1]) == row["drill_mm"]]
        assert len(candidates) == 1, ("Preceding USB geometry changed", row)
        tree.remove(candidates[0])
    assert len(data["removed_copper"]) == 8
    assert {r["net"] for r in data["removed_copper"]} == {"lv", "connector-1"}
    prep = folder / "usb-data-prepared.kicad_pcb"
    prep.write_text(dumps(tree) + "\n")
    shutil.copyfile(source.with_suffix(".kicad_pro"), prep.with_suffix(".kicad_pro"))
    b = pcbnew.LoadBoard(str(prep))
    parts = {f.GetFieldText("atopile_address"): f for f in b.GetFootprints()}
    incoming = {t.m_Uuid.AsString(): signature(t) for t in b.GetTracks()}
    for address, target in data["final_placement"].items():
        old = data["old_placement"][address]
        f = parts[address]
        assert f.GetPosition() == point(old["uv"])
        assert f.GetOrientationDegrees() % 360 == old["rotation"] % 360
        f.SetPosition(point(target["uv"]))
        f.SetOrientationDegrees(target["rotation"])
    layers = {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu}
    nets = b.GetNetsByName()
    added = []
    for route in data["routes"]:
        for a, c in zip(route["path"], route["path"][1:]):
            assert a != c
            t = pcbnew.PCB_TRACK(b)
            t.SetStart(point(a)); t.SetEnd(point(c))
            t.SetWidth(round(route["width"] * 1e6))
            t.SetLayer(layers[route["layer"]])
            t.SetNet(nets[route["net"]]); b.Add(t); added.append(t)
    positions = {(t.GetPosition().x, t.GetPosition().y) for t in b.GetTracks()
                 if isinstance(t, pcbnew.PCB_VIA)}
    for row in data["vias"]:
        p = point(row["xy"])
        assert (p.x, p.y) not in positions
        positions.add((p.x, p.y))
        v = pcbnew.PCB_VIA(b); v.SetPosition(p)
        v.SetWidth(round(row["d"] * 1e6)); v.SetDrill(round(row["h"] * 1e6))
        v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetNet(nets[row["net"]]); b.Add(v); added.append(v)
    row = data["return_zone"]
    z = pcbnew.ZONE(b); z.SetLayer(pcbnew.In2_Cu)
    z.SetNet(nets[row["net"]]); z.SetZoneName(row["name"])
    z.SetLocalClearance(round(row["clearance_mm"] * 1e6))
    z.SetThermalReliefGap(200000); z.SetThermalReliefSpokeWidth(200000)
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL); z.SetMinThickness(150000)
    z.Outline().NewOutline()
    for p in row["uvs"]:
        z.Outline().Append(point(p))
    b.Add(z)
    before_fill = {t.m_Uuid.AsString(): signature(t) for t in b.GetTracks()}
    assert all(before_fill[k] == v for k, v in incoming.items())
    b.BuildConnectivity(); pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(str(out), b)
    # Filling and saving must not silently reassign any overlapping via's net.
    saved = pcbnew.LoadBoard(str(out))
    assert {t.m_Uuid.AsString(): signature(t) for t in saved.GetTracks()} == before_fill
    shutil.copyfile(source.with_suffix(".kicad_pro"), out.with_suffix(".kicad_pro"))
    assert board_graph(source) == board_graph(out)
    assert source.read_bytes() == source_bytes
    print("USB data: eight exact old items replaced; ESD moved; saved ground fill and all other incoming copper preserved.")


if __name__ == "__main__":
    main()
