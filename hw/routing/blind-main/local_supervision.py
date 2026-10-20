"""Append the local control paths to the current protected USB routing stage."""
from pathlib import Path
import json
import shutil
import sys
import pcbnew
import wx
from regen import signature

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from generate_schematics import board_graph


def point(uv):
    return pcbnew.VECTOR2I(pcbnew.FromMM(100 + uv[0]),
                          pcbnew.FromMM(175 - uv[1]))


def main():
    app = wx.App(False)
    quiet = wx.LogNull()
    work = ROOT / "work/main-route-build"
    source = work / "usb-data.kicad_pcb"
    out = work / "local-supervision.kicad_pcb"
    source_bytes = source.read_bytes()
    data = json.loads((HERE / "local-supervision-routes.json").read_text())
    b = pcbnew.LoadBoard(str(source))
    parts = {f.GetFieldText("atopile_address"): f for f in b.GetFootprints()}
    incoming = {t.m_Uuid.AsString(): signature(t) for t in b.GetTracks()}
    for address, target in data["final_placement"].items():
        f = parts[address]
        old = data["old_placement"][address]
        assert max(abs(a-c) for a,c in zip(
            (f.GetPosition().x, f.GetPosition().y),
            (point(old["uv"]).x, point(old["uv"]).y))) <= 1
        assert f.GetOrientationDegrees() % 360 == old["rotation"] % 360
        f.SetPosition(point(target["uv"]))
        f.SetOrientationDegrees(target["rotation"])
    layers = {"F": pcbnew.F_Cu, "B": pcbnew.B_Cu, "I": pcbnew.In2_Cu}
    nets = b.GetNetsByName()
    positions = {(t.GetPosition().x, t.GetPosition().y): t
                 for t in b.GetTracks() if isinstance(t, pcbnew.PCB_VIA)}
    for row in data["routes"]:
        for a, c in zip(row["path"], row["path"][1:]):
            if a[2] == c[2]:
                if a[:2] == c[:2]:
                    continue
                t = pcbnew.PCB_TRACK(b)
                t.SetStart(point(a[:2])); t.SetEnd(point(c[:2]))
                t.SetWidth(round(row.get("width_mm", .15) * 1e6))
                t.SetLayer(layers[a[2]]); t.SetNet(nets[row["net"]]); b.Add(t)
            else:
                assert a[:2] == c[:2]
                p = point(a[:2]); key = (p.x, p.y)
                if key in positions:
                    assert positions[key].GetNetname() == row["net"]
                    continue
                v = pcbnew.PCB_VIA(b); v.SetPosition(p)
                v.SetWidth(500000); v.SetDrill(250000)
                v.SetViaType(pcbnew.VIATYPE_THROUGH)
                v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
                v.SetNet(nets[row["net"]]); b.Add(v); positions[key] = v
    before_fill = {t.m_Uuid.AsString(): signature(t) for t in b.GetTracks()}
    assert all(before_fill[k] == value for k, value in incoming.items())
    b.BuildConnectivity(); pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(str(out), b)
    shutil.copyfile(source.with_suffix(".kicad_pro"), out.with_suffix(".kicad_pro"))
    saved = pcbnew.LoadBoard(str(out))
    actual = {t.m_Uuid.AsString(): signature(t) for t in saved.GetTracks()}
    assert actual == before_fill, "Fill/save changed an existing or added copper item"
    assert board_graph(source) == board_graph(out), "Circuit graph changed"
    assert source.read_bytes() == source_bytes, "Incoming stage was modified"
    print(json.dumps({"incoming_copper_preserved": len(incoming),
                      "added_copper": len(actual)-len(incoming)}))


if __name__ == "__main__":
    main()
