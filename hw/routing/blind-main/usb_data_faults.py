"""USB-specific open, return and stale-filled-geometry fault controls."""
from pathlib import Path
import copy, tempfile
import pcbnew
from kicad_sexpr import parse, dumps, children, one
from usb_data_checks import verify


def run(source, checks):
    original = parse(source.read_text())
    results = []
    def reject(name, change):
        tree = copy.deepcopy(original)
        change(tree)
        with tempfile.TemporaryDirectory(prefix="usb-fault-") as folder:
            path = Path(folder)/"fault.kicad_pcb"
            path.write_text(dumps(tree)+"\n")
            board = pcbnew.LoadBoard(str(path))
            try:
                verify(board, checks)
            except AssertionError:
                results.append(name+" rejected")
            else:
                raise AssertionError("USB fault escaped: "+name)
    def cut(tree, net, a, c):
        def close(value, expected):
            return max(abs(float(v)-e) for v, e in zip(value, expected)) < .000002
        found = [n for n in children(tree, "segment")
                 if one(n, "net")[1] == net and one(n, "layer")[1] == "F.Cu"
                 and close(one(n, "start")[1:], a)
                 and close(one(n, "end")[1:], c)]
        assert len(found) == 1, (net, a, c)
        tree.remove(found[0])
    reject("cut D-plus perimeter", lambda t: cut(t, "usb_dp", [100.9,150.2], [100.9,124.7]))
    reject("cut D-minus contact A7", lambda t: cut(t, "usb_dm", [129.75,170.68], [129.75,169.4]))
    reject("cut ESD ground via feed", lambda t: cut(t, "lv", [122.1,172.8], [121.4,172.8]))
    def lose_back_plane(t):
        zone = next(z for z in children(t, "zone")
                    if one(z, "name") and one(z, "name")[1] == "USB_LOCAL_IN2_RETURN")
        t.remove(zone)
    reject("remove back crossover reference", lose_back_plane)
    def stale_fill(t):
        zone = next(z for z in children(t, "zone")
                    if one(z, "name") and one(z, "name")[1] == "TRIAL_IN1_GND_RETURN")
        zone.append(parse('(filled_polygon (layer "In1.Cu") (pts (xy 129.75 172) (xy 129.95 172) (xy 129.95 172.2) (xy 129.75 172.2)))'))
    reject("restore saved ground across D-minus via antipad", stale_fill)
    def bypass(t):
        points = [(124.5,172.75),(124.5,170.5),(122.8,170.5),(122.8,171.9)]
        for i, (a, c) in enumerate(zip(points, points[1:])):
            t.append(parse(f'(segment (start {a[0]} {a[1]}) (end {c[0]} {c[1]}) '
                           f'(width 0.15) (layer "F.Cu") (net "usb_dp") '
                           f'(uuid "084515a7-0960-4e05-a428-5da88674304{i}"))'))
    reject("add longer D-plus bypass around ESD pad", bypass)
    return results
