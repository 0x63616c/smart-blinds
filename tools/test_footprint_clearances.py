"""Fault tests for clearance generation and compiled-outline verification.

All board and source mutations use temporary fixtures. These tests do not read
or rebuild the production PCBs and do not qualify the package envelopes.
"""
from contextlib import redirect_stdout
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import check_footprint_clearances as checker
import complete_courtyards as generator
from kicad_sexpr import Atom, children, dumps, node, one, parse


BOX = [-2.0, -0.5, 2.0, 0.5]
ALIAS = "fixture:rectangle"


def footprint(address="part", box=BOX, angle=0, layer="F.Cu"):
    fp = node(
        "footprint", ALIAS, node("layer", layer), node("at", 110, 155, angle),
        node("property", "Reference", "U1"),
        node("property", "atopile_address", address),
        node("attr", Atom("smd")),
        node("pad", "1", Atom("smd"), Atom("rect"),
             node("at", -0.4, 0), node("size", 0.3, 0.4),
             node("layers", "F.Cu", "F.Paste", "F.Mask"), node("net", 1, "P")),
        node("pad", "2", Atom("smd"), Atom("rect"),
             node("at", 0.4, 0), node("size", 0.3, 0.4),
             node("layers", "F.Cu", "F.Paste", "F.Mask"), node("net", 2, "N")),
    )
    if box is not None:
        fp.append(generator.drawing(box, "fixture"))
    return parse(dumps(fp))


def without_courtyard(fp):
    return [item for item in fp if item not in generator.courtyard_items(fp)]


class ClearanceBoardTests(unittest.TestCase):
    def test_retained_envelope_cannot_shrink_body_or_land_clearance(self):
        entry={'body_lead_bounds_mm':[-1,-1,1,1], 'clearance_margin_mm':.25,
               'retained_courtyard_bounds_mm':[-1.5,-1.5,1.5,1.5]}
        self.assertEqual(generator.bounds(footprint(),entry),[-1.5,-1.5,1.5,1.5])
        for bad in ([-1,-1.5,1.5,1.5],[-1.5,-1.5,1.2,1.5],
                    [-1.51,-1.5,1.5,1.5],[float('nan'),-1.5,1.5,1.5]):
            with self.subTest(bounds=bad), self.assertRaisesRegex(ValueError,'Retained courtyard'):
                generator.bounds(footprint(),dict(entry,retained_courtyard_bounds_mm=bad))

    def test_compiled_pad_rotation_is_relative_to_parent_before_containment(self):
        fp=footprint(angle=90)
        for pad in children(fp,'pad'):
            one(pad,'at').append(Atom('90'))
            one(pad,'size')[1:]=[Atom('1.2'),Atom('.2')]
        actual=checker.compiled_pad_bounds(fp)
        self.assertEqual(actual,[-1.0,-.1,1.0,.1])
        checker.check_pad_containment(fp,[-1,-.1,1,.1])
        with self.assertRaisesRegex(ValueError,'omits pad extent'):
            checker.check_pad_containment(fp,[-.9,-.6,.9,.6])

    def test_compiled_custom_polygon_without_stroke_has_valid_bounds(self):
        fp=parse('''(footprint "fixture:custom" (at 110 155 90)
          (pad "1" smd custom (at 0 0 90) (size 0.01 0.01)
            (layers "F.Cu") (primitives
              (gr_poly (pts (xy -1 -0.2) (xy 1 -0.2)
                (xy 1 0.2) (xy -1 0.2)) (fill yes)))))''')
        self.assertEqual(checker.compiled_pad_bounds(fp),[-1,-.2,1,.2])
        with self.assertRaisesRegex(ValueError,'omits pad extent'):
            checker.check_pad_containment(fp,[-.9,-.3,.9,.3])

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.placement = self.root / "hw/placement/blind-main/placement.json"
        self.placement.parent.mkdir(parents=True)
        self.placement.write_text(json.dumps({"reserved": []}))

    def check(self, *parts, expected=None, count=None):
        board = self.root / "fixture.kicad_pcb"
        board.write_text(dumps(node("kicad_pcb", *parts)))
        expected = {ALIAS: BOX} if expected is None else expected
        count = len(parts) if count is None else count
        with patch.object(checker, "ROOT", self.root), patch.dict(
            checker.COUNTS, {"main": count}
        ):
            return checker.check_board("main", board, expected)

    def reserve(self, label, box):
        self.placement.write_text(json.dumps({"reserved": [[label, box]]}))

    def test_complete_fixture_counts_outline_coverage(self):
        self.assertEqual(self.check(footprint()), {
            "electrical_footprints": 1,
            "with_courtyards": 1,
            "new_envelopes_checked": 1,
        })

    def test_missing_courtyard_rejected_even_for_unrepaired_alias(self):
        with self.assertRaisesRegex(ValueError, "Missing courtyard"):
            self.check(footprint(box=None), expected={})

    def test_unreviewed_alias_cannot_hide_its_pad_tips(self):
        with self.assertRaisesRegex(ValueError,'omits pad extent'):
            self.check(footprint(box=[-.5,-.2,.5,.2]),expected={})

    def test_shrunken_reviewed_courtyard_rejected(self):
        with self.assertRaisesRegex(ValueError, "reviewed envelope"):
            self.check(footprint(box=[-1.9, -0.5, 2, 0.5]))

    def test_duplicate_address_cannot_mask_an_extra_component(self):
        with self.assertRaisesRegex(ValueError, "Duplicate electrical address"):
            self.check(footprint(), footprint())

    def test_missing_electrical_address_rejected(self):
        fp = footprint()
        fp = [
            item for item in fp
            if not (isinstance(item, list) and item[:2] == ["property", "atopile_address"])
        ]
        with self.assertRaisesRegex(ValueError, "without an electrical address"):
            self.check(fp)

    def test_component_count_change_rejected(self):
        with self.assertRaisesRegex(ValueError, "component count"):
            self.check(footprint(), count=2)

    def test_rotated_part_uses_board_to_enclosure_coordinates(self):
        # Footprint at (110,155) maps to (u10,v20). A positive 90-degree
        # rotation puts its long X axis along enclosure +v.
        actual = checker.placed_bounds(footprint(angle=90), BOX)
        for value, expected in zip(actual, [9.5, 18, 10.5, 22]):
            self.assertAlmostEqual(value, expected)

    def test_rotated_part_intrudes_into_encoder_cable_corridor(self):
        self.reserve("encoder-cable", [9.6, 21.5, 10.4, 22.5])
        with self.assertRaisesRegex(ValueError, "reserved encoder-cable"):
            self.check(footprint(angle=90))

    def test_only_the_named_connector_gets_its_corridor_exception(self):
        self.reserve("encoder-cable", [9.6, 21.5, 10.4, 22.5])
        self.check(footprint("encoder_port.header", angle=90))
        with self.assertRaisesRegex(ValueError, "reserved encoder-cable"):
            self.check(
                footprint("encoder_port.header", angle=90),
                footprint("nearby_resistor", angle=90),
            )

    def test_connector_exception_does_not_apply_to_a_different_corridor(self):
        self.reserve("battery-plug", [9.6, 21.5, 10.4, 22.5])
        with self.assertRaisesRegex(ValueError, "reserved battery-plug"):
            self.check(footprint("encoder_port.header", angle=90))

    def test_tangent_bounds_are_not_positive_area_overlap(self):
        self.assertFalse(checker.intersects([0, 0, 1, 1], [1, 0, 2, 1]))
        self.assertTrue(checker.intersects([0, 0, 1, 1], [0.999, 0, 2, 1]))

    def test_nonfinite_courtyard_cannot_bypass_envelope_or_corridor(self):
        for value in ("nan", "inf", "-inf"):
            with self.subTest(value=value):
                fp = footprint()
                rect = generator.courtyard_items(fp)[0]
                one(rect, "start")[1] = Atom(value)
                with self.assertRaises(ValueError):
                    self.check(fp)

    def test_nonfinite_placement_cannot_bypass_reserved_corridor(self):
        self.reserve("encoder-cable", [9, 19, 11, 21])
        for coordinate in (1, 2, 3):
            with self.subTest(coordinate=coordinate):
                fp = footprint()
                one(fp, "at")[coordinate] = Atom("nan")
                with self.assertRaises(ValueError):
                    self.check(fp)

    def test_back_side_part_cannot_use_front_only_transform(self):
        with self.assertRaises(ValueError):
            self.check(footprint(layer="B.Cu"))


class ClearanceSourceTests(unittest.TestCase):
    def test_replacement_requires_exact_reviewed_original_and_preserves_pads(self):
        fp=footprint(box=[-.5,-.25,.5,.25])
        original=copy.deepcopy(fp)
        expected=generator.drawing(BOX,'replacement-fixture')
        entry={'replace_courtyard_sha256':{'fixture':generator.geometry_hash(generator.courtyard_items(fp))}}
        self.assertTrue(generator.update_outline(fp,expected,entry,'fixture',False))
        self.assertEqual(without_courtyard(fp),without_courtyard(original))
        self.assertEqual(children(fp,'pad'),children(original,'pad'))
        self.assertFalse(generator.update_outline(fp,expected,entry,'fixture',True))
        changed=copy.deepcopy(original)
        one(generator.courtyard_items(changed)[0],'start')[1]=Atom('-.6')
        for reviewed in (entry,{}):
            with self.subTest(reviewed=reviewed),self.assertRaisesRegex(ValueError,'reviewed original'):
                generator.update_outline(changed,expected,reviewed,'fixture',False)

    def test_check_mode_never_applies_a_reviewed_replacement(self):
        fp=footprint(box=[-.5,-.25,.5,.25])
        original=copy.deepcopy(fp)
        entry={'replace_courtyard_sha256':{'fixture':generator.geometry_hash(generator.courtyard_items(fp))}}
        with self.assertRaisesRegex(ValueError,'unreviewed courtyard'):
            generator.update_outline(fp,generator.drawing(BOX,'fixture'),entry,'fixture',True)
        self.assertEqual(fp,original)

    def test_pad_fingerprint_distinguishes_plating_and_pin_mapping(self):
        original=footprint()
        expected=generator.geometry_hash(children(original,'pad'))
        for field,value in ((1,'2'),(2,Atom('np_thru_hole'))):
            changed=copy.deepcopy(original)
            children(changed,'pad')[0][field]=value
            self.assertNotEqual(generator.geometry_hash(children(changed,'pad')),expected)

    def test_rotated_custom_polygon_includes_full_stroke(self):
        fp = parse('''(footprint "custom"
          (pad "1" smd custom (at 10 20 90) (size 0.01 0.01)
            (layers "F.Cu")
            (primitives
              (gr_poly (pts (xy 0 0) (xy 2 0) (xy 2 1) (xy 0 1))
                (width 0.2) (fill yes)))))''')
        actual = generator.pad_bounds(fp)
        for value, expected in zip(actual, [9.9, 17.9, 11.1, 20.1]):
            self.assertAlmostEqual(value, expected)
        # A lost stroke must change the resulting envelope, even though the
        # anchor and all polygon vertices are identical.
        damaged = copy.deepcopy(fp)
        polygon = one(one(one(damaged, "pad"), "primitives"), "gr_poly")
        one(polygon, "width")[1] = Atom("0")
        self.assertNotEqual(generator.pad_bounds(damaged), actual)
        self.assertEqual(generator.bounds(fp, {
            "body_lead_bounds_mm": [9.99, 19.99, 10.01, 20.01],
            "clearance_margin_mm": 0.25,
        }), [9.65, 17.65, 11.35, 20.35])

    def test_unsupported_custom_geometry_is_rejected(self):
        fp = parse('''(footprint "custom"
          (pad "1" smd custom (at 0 0) (size 0.01 0.01)
            (layers "F.Cu")
            (primitives (gr_circle (center 0 0) (end 1 0)
              (width 0.1) (fill yes)))))''')
        with self.assertRaisesRegex(ValueError, "Unsupported custom-pad"):
            generator.pad_bounds(fp)

    def test_source_generation_is_idempotent_and_preserves_every_pad(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, mirror = root / "part.kicad_mod", root / "mirror.kicad_mod"
            initial = footprint(box=None)
            source.write_text(dumps(initial))
            mirrored = copy.deepcopy(initial)
            mirrored[1] = "mirror:rectangle"
            mirrored.append(node("model", "../mirror-only-model.step"))
            mirror.write_text(dumps(mirrored))
            plan = root / "plan.json"
            plan.write_text(json.dumps({"footprints": [{
                "source": source.name, "mirrors": [mirror.name],
                "body_lead_bounds_mm": [-0.5, -0.25, 0.5, 0.25],
                "clearance_margin_mm": 0.25,
                "envelope_status": "test_fixture",
            }]}))
            with patch.object(generator, "ROOT", root), patch.object(generator, "PLAN", plan):
                with patch("sys.argv", ["complete_courtyards.py"]), redirect_stdout(io.StringIO()):
                    generator.main()
                after = {p: p.read_bytes() for p in (source, mirror)}
                for p, before in ((source, initial), (mirror, parse(dumps(mirrored)))):
                    actual = parse(p.read_text())
                    self.assertEqual(without_courtyard(actual), before)
                    self.assertEqual(children(actual, "pad"), children(before, "pad"))
                    self.assertEqual(len(generator.courtyard_items(actual)), 1)
                # Parsed numeric atoms must compare with the generated
                # normalized node; this catches the original idempotency bug.
                for args in (["complete_courtyards.py", "--check"], ["complete_courtyards.py"]):
                    with patch("sys.argv", args), redirect_stdout(io.StringIO()):
                        generator.main()
                    self.assertEqual({p: p.read_bytes() for p in (source, mirror)}, after)


class DrcReportTests(unittest.TestCase):
    def report(self, *types):
        return {'violations':[{'type':kind} for kind in types], 'unconnected_items':[{}],
                'included_severities':['error','warning','exclusion'],
                'ignored_checks':[{'key':'missing_courtyard'}]}

    def test_each_assembly_failure_rejected(self):
        for kind in checker.ASSEMBLY_FAILURES:
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError,'Assembly clearance DRC failed'):
                checker.check_drc_report(self.report(kind))

    def test_unrouted_and_manufacturing_findings_remain_visible(self):
        result=checker.check_drc_report(self.report('silk_over_copper','clearance'))
        self.assertEqual(result['remaining_violations'],{'silk_over_copper':1,'clearance':1})
        self.assertEqual(result['unconnected_items'],1)

    def test_incomplete_report_rejected(self):
        for key in ('violations','unconnected_items','included_severities'):
            report=self.report();del report[key]
            with self.subTest(key=key), self.assertRaises(ValueError):checker.check_drc_report(report)

    def test_disabled_assembly_category_rejected(self):
        for kind in checker.ASSEMBLY_FAILURES-{'missing_courtyard'}:
            report=self.report();report['ignored_checks'].append({'key':kind})
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError,'category is disabled'):
                checker.check_drc_report(report)


class OverboardWireTests(unittest.TestCase):
    def test_actual_cad_route_matches_and_moved_route_is_rejected(self):
        source=(checker.ROOT/'cad/source/compact_retained.scad').read_text()
        controller=json.loads((checker.ROOT/'cad/parameters/retained-interfaces.json').read_text())['controller']
        checker.check_wire_source(source,controller)
        changed=source.replace('[110,encoder_transition_y,57]','[108,encoder_transition_y,57]')
        self.assertNotEqual(changed,source)
        with self.assertRaises(ValueError):checker.check_wire_source(changed,controller)

    def check(self,fp,**changes):
        contract={'local_uv':[9,19,11,21],'component_face_x':100.6,'nearest_wire_x':108.9,
                  'clearance':.5,'maximum_mounted_component_height':7.8}
        contract.update(changes)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'board.kicad_pcb';path.write_text(dumps(node('kicad_pcb',fp)))
            return checker.check_overboard_wire(path,contract)

    def reviewed(self):
        fp=footprint('controller.r_down');fp[1]='UNI_ROYAL_0402WGF1002TCE:R0402'
        fp.append(node('property','LCSC','C25744'));return fp

    def test_exact_reviewed_part_passes(self):
        self.assertEqual(self.check(self.reviewed())['reviewed_parts_under_route'],['controller.r_down'])

    def test_unknown_part_or_substitution_rejected(self):
        for edit in ('name','alias','part'):
            fp=self.reviewed()
            if edit=='name':
                next(p for p in children(fp,'property') if p[1]=='atopile_address')[2]='new.part'
            elif edit=='alias':fp[1]='tall:0402'
            else:next(p for p in children(fp,'property') if p[1]=='LCSC')[2]='C00000'
            with self.subTest(edit=edit),self.assertRaisesRegex(ValueError,'Unreviewed or too-tall'):
                self.check(fp)

    def test_geometry_and_too_low_height_rejected(self):
        for changes in ({'nearest_wire_x':float('nan')},{'maximum_mounted_component_height':8},
                        {'nearest_wire_x':101.6,'maximum_mounted_component_height':.5}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):self.check(self.reviewed(),**changes)


if __name__ == "__main__":
    unittest.main()
