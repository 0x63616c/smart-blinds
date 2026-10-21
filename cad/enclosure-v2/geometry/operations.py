"""Shared geometry checks. No runtime AST extraction or historical imports."""

import math,itertools,numpy as np

from functools import partial



def overlap(a, b, tol=1e-05):
    return bool(np.all(np.minimum(a[3:], b[3:]) - np.maximum(a[:3], b[:3]) > tol))

def inside_mesh(point, tris):
    d = np.array([1.0, 0.371390676354, 0.694746590606])
    e1, e2 = (tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    p = np.cross(d, e2)
    det = np.sum(e1 * p, axis=1)
    keep = np.abs(det) > 1e-10
    inv = np.zeros(len(det))
    inv[keep] = 1 / det[keep]
    s = point - tris[:, 0]
    u = np.sum(s * p, axis=1) * inv
    q = np.cross(s, e1)
    v = q @ d * inv
    t = np.sum(e2 * q, axis=1) * inv
    hit = keep & (u >= -1e-08) & (v >= -1e-08) & (u + v <= 1 + 1e-08) & (t > 1e-08)
    ts = np.sort(t[hit])
    return bool(len(ts) and (1 + np.count_nonzero(np.diff(ts) > 1e-07)) % 2)

def mesh_box(tris, box):
    """Triangle/AABB separating axes plus closed-mesh containment."""
    box = np.array(box)
    center, half = ((box[:3] + box[3:]) / 2, (box[3:] - box[:3]) / 2)
    broad = np.all(tris.max(1) >= box[:3] + 1e-06, axis=1) & np.all(tris.min(1) <= box[3:] - 1e-06, axis=1)
    t = tris[broad] - center
    if len(t):
        e = np.stack([t[:, 1] - t[:, 0], t[:, 2] - t[:, 1], t[:, 0] - t[:, 2]], axis=1)
        axes = [np.broadcast_to(a, (len(t), 3)) for a in np.eye(3)]
        axes += [np.cross(e[:, 0], e[:, 1])]
        axes += [np.cross(e[:, j], a) for j in range(3) for a in np.eye(3)]
        separated = np.zeros(len(t), dtype=bool)
        for a in axes:
            norm = np.linalg.norm(a, axis=1)
            projection = np.einsum('nvc,nc->nv', t, a)
            radius = np.abs(a) @ half
            separated |= (norm > 1e-12) & ((projection.min(1) > radius - 1e-07 * norm) | (projection.max(1) < -radius + 1e-07 * norm))
        if np.any(~separated):
            return True
    return inside_mesh(center, tris)

def box_faces(q):
    lo, hi = (np.array(q[:3]), np.array(q[3:]))
    v = np.array(list(itertools.product(*zip(lo, hi))))
    return [v[ix] for ix in ([0, 1, 3, 2], [4, 6, 7, 5], [0, 4, 5, 1], [2, 3, 7, 6], [0, 2, 6, 4], [1, 5, 7, 3])]

def point_seg(p, a, b):
    d = b - a
    t = np.clip(np.sum((p - a) * d, axis=-1) / np.maximum(np.sum(d * d, axis=-1), 1e-30), 0, 1)
    return np.sum((p - (a + t[..., None] * d)) ** 2, axis=-1)

def point_tri(p, t):
    a, b, c = (t[:, 0], t[:, 1], t[:, 2])
    ab = b - a
    ac = c - a
    n = np.cross(ab, ac)
    nn = np.sum(n * n, axis=1)
    h = np.sum((p - a) * n, axis=1) / np.maximum(nn, 1e-30)
    q = p - h[:, None] * n
    v0 = ab
    v1 = ac
    v2 = q - a
    d00 = np.sum(v0 * v0, axis=1)
    d01 = np.sum(v0 * v1, axis=1)
    d11 = np.sum(v1 * v1, axis=1)
    d20 = np.sum(v2 * v0, axis=1)
    d21 = np.sum(v2 * v1, axis=1)
    den = d00 * d11 - d01 * d01
    vv = (d11 * d20 - d01 * d21) / np.maximum(den, 1e-30)
    ww = (d00 * d21 - d01 * d20) / np.maximum(den, 1e-30)
    plane = np.where((nn > 1e-24) & (vv >= -1e-12) & (ww >= -1e-12) & (vv + ww <= 1 + 1e-12), h * h * nn, np.inf)
    return np.minimum(plane, np.minimum.reduce([point_seg(p, a, b), point_seg(p, b, c), point_seg(p, c, a)]))

def segment_segment(p, q, a, b):
    u = q - p
    v = b - a
    w = p - a
    aa = u @ u
    bb = v @ u
    cc = np.sum(v * v, axis=1)
    dd = w @ u
    ee = np.sum(v * w, axis=1)
    den = aa * cc - bb * bb
    s = (bb * ee - cc * dd) / np.where(np.abs(den) > 1e-25, den, 1)
    t = (aa * ee - bb * dd) / np.where(np.abs(den) > 1e-25, den, 1)
    interior = np.where((den > 1e-25) & (s >= 0) & (s <= 1) & (t >= 0) & (t <= 1), np.sum((w + s[:, None] * u - t[:, None] * v) ** 2, axis=1), np.inf)
    return np.minimum(interior, np.minimum.reduce([point_seg(p, a, b), point_seg(q, a, b), point_seg(a, p, q), point_seg(b, p, q)]))

def seg_tri(p, q, t):
    out = np.minimum(point_tri(p, t), point_tri(q, t))
    for i in range(3):
        out = np.minimum(out, segment_segment(p, q, t[:, i], t[:, (i + 1) % 3]))
    n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
    den = n @ (q - p)
    s = np.sum(n * (t[:, 0] - p), axis=1) / np.where(abs(den) > 1e-20, den, 1)
    inter = p + s[:, None] * (q - p)
    on = (abs(den) > 1e-20) & (s >= 0) & (s <= 1) & (point_tri(inter, t) < 1e-18)
    return np.where(on, 0, out)

def tri_tri(a, ts):
    out = np.full(len(ts), np.inf)
    for i in range(3):
        out = np.minimum(out, seg_tri(a[i], a[(i + 1) % 3], ts))
    for j, t in enumerate(ts):
        for i in range(3):
            out[j] = min(out[j], seg_tri(t[i], t[(i + 1) % 3], a[None, :])[0])
    return out

def near(path, rad, mesh):
    lo = mesh.min(1)
    hi = mesh.max(1)
    best = 3.0
    wit = None
    for i, (p, q) in enumerate(zip(path[:-1], path[1:])):
        ix = np.where(np.all(hi >= np.minimum(p, q) - rad - best, axis=1) & np.all(lo <= np.maximum(p, q) + rad + best, axis=1))[0]
        if not len(ix):
            continue
        ds = seg_tri(p, q, mesh[ix])
        m0 = math.sqrt(max(0, float(ds.min()))) - rad
        if m0 < best:
            best = m0
            wit = {'segment': i, 'from': p.tolist(), 'to': q.tolist(), 'triangle': mesh[ix[int(ds.argmin())]].tolist()}
    return (best, wit)

def boxdist(p, q, box):
    lo, hi = (box[:3], box[3:])
    d = q - p
    cuts = [0.0, 1.0]
    for i in range(3):
        if abs(d[i]) > 1e-15:
            cuts.extend((t for v in [lo[i], hi[i]] if 0 < (t := ((v - p[i]) / d[i])) < 1))
    cuts = sorted(set(cuts))
    best = math.inf
    for a, b in zip(cuts[:-1], cuts[1:]):
        m = p + (a + b) / 2 * d
        target = np.clip(m, lo, hi)
        active = (m < lo) | (m > hi)
        dd = d[active]
        pp = p[active] - target[active]
        t = np.clip(-float(pp @ dd) / float(dd @ dd), a, b) if float(dd @ dd) > 0 else a
        v = p + t * d
        best = min(best, float(np.linalg.norm(v - np.clip(v, lo, hi))))
    return best

def cylinder_clearance(w, x, y0, y1, z, r, hexagon=False):
    a = w[:-1]
    d = w[1:] - a

    def ds(t):
        q = a + t[:, None] * d
        points = q[:, [0, 2]] - [x, z]
        rad = np.maximum(np.linalg.norm(points, axis=1) - r, 0)
        if hexagon:
            vertices = np.array([[r * math.cos(ang), r * math.sin(ang)] for ang in np.arange(6) * math.pi / 3 + math.pi / 6])
            dd = []
            cross = []
            for aa, bb in zip(vertices, np.roll(vertices, -1, axis=0)):
                edge = bb - aa
                tt = np.clip((points - aa) @ edge / (edge @ edge), 0, 1)
                dd.append(np.linalg.norm(points - aa - tt[:, None] * edge, axis=1))
                cross.append(edge[0] * (points[:, 1] - aa[1]) - edge[1] * (points[:, 0] - aa[0]))
            rad = np.where(np.all(np.array(cross) >= -1e-10, axis=0), 0, np.min(dd, axis=0))
        ax = np.maximum(np.maximum(y0 - q[:, 1], q[:, 1] - y1), 0)
        return rad * rad + ax * ax
    lo = np.zeros(len(a))
    hi = np.ones(len(a))
    g = (math.sqrt(5) - 1) / 2
    for _ in range(70):
        c = hi - g * (hi - lo)
        e = lo + g * (hi - lo)
        choose = ds(c) < ds(e)
        hi = np.where(choose, e, hi)
        lo = np.where(choose, lo, c)
    return math.sqrt(float(np.minimum.reduce([ds((lo + hi) / 2), ds(np.zeros(len(a))), ds(np.ones(len(a)))]).min())) - 0.93

def wires(a, ra, b, rb):
    best = 3.0 + ra + rb
    lo = np.minimum(b[:-1], b[1:])
    hi = np.maximum(b[:-1], b[1:])
    for p, q in zip(a[:-1], a[1:]):
        gap = np.maximum(np.maximum(lo - np.maximum(p, q), np.minimum(p, q) - hi), 0)
        ix = np.where(np.einsum('ij,ij->i', gap, gap) <= best * best)[0]
        if len(ix):
            best = min(best, math.sqrt(max(0, float(segment_segment(p, q, b[ix], b[ix + 1]).min()))))
    return best - ra - rb

def surface_sweep(t, vec):
    v = np.array(vec)
    tri = [t, t + v]
    for i, j in [(0, 1), (1, 2), (2, 0)]:
        tri.extend([np.stack([t[:, i], t[:, j], t[:, j] + v], 1), np.stack([t[:, i], t[:, j] + v, t[:, i] + v], 1)])
    out = np.concatenate(tri)
    return out[np.linalg.norm(np.cross(out[:, 1] - out[:, 0], out[:, 2] - out[:, 0]), axis=1) > 1e-10]

def swept_check(q, tri, vec, obstacle, name, rows):
    from manifold3d import Manifold, Error
    vec = np.array(vec)
    parts = obstacle.decompose()
    bbs = [np.array(p.bounding_box()) for p in parts]
    hits = []
    count = 0
    for idx, p in enumerate(parts):
        for pose in [np.zeros(3), vec]:
            it = q.translate(pose) ^ p
            assert it.status() == Error.NoError
            if not it.is_empty():
                hits.append({'endpoint': pose.tolist(), 'volume_mm3': it.volume(), 'bounds': it.bounding_box()})
    for i, t in enumerate(tri):
        if abs(np.cross(t[1] - t[0], t[2] - t[0]) @ vec) < 1e-10:
            continue
        pts = np.vstack([t, t + vec])
        lo = pts.min(0)
        hi = pts.max(0)
        candidates = [j for j, b in enumerate(bbs) if np.all(hi >= b[:3]) and np.all(lo <= b[3:])]
        if not candidates:
            continue
        prism = Manifold.hull_points(pts)
        assert prism.status() == Error.NoError
        count += 1
        for j in candidates:
            it = prism ^ parts[j]
            assert it.status() == Error.NoError
            if not it.is_empty():
                hits.append({'triangle': i, 'volume_mm3': it.volume(), 'bounds': it.bounding_box()})
    rows.append({'name': name, 'extruded_surface_prisms': count, 'findings': hits, 'pass': not hits})
    print(name, count, 'findings', len(hits), flush=True)

def into(names, environment):
    """Explicit compatibility adapter while checks migrate to direct imports."""
    for name in names:
        value = globals()[name]
        if name == "swept_check":
            value = partial(value, rows=environment["rows"])
        environment[name] = value
