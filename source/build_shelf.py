"""Run inside FreeCAD: exec(open(path, encoding='utf-8').read())."""
from pathlib import Path
import json
import FreeCAD as App
import FreeCADGui as Gui
import Part
import MeshPart

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / 'models'
EXPORTS = ROOT / 'exports' / 'current'
REPORTS = ROOT / 'reports' / 'current'
for folder in (MODELS, EXPORTS, REPORTS):
    folder.mkdir(parents=True, exist_ok=True)
VERSION = 'v3'
LENGTH, WIDTH, PLATE = 200.0, 250.0, 4.0  # X crosses board; Y runs along board.
BOARD = 28.7
CLEARANCE = 0.2  # Total clearance, pending print measurement.
INNER = 55.0
OUTER = INNER + BOARD + CLEARANCE
DEPTH = 90.0
WALL = 5.0
RIB_DEPTH, RIB_THICKNESS = 50.0, 4.0
V = App.Vector


def box(x, y, z, dx, dy, dz):
    return Part.makeBox(dx, dy, dz, V(x, y, z))


def profile(points, y, width):
    vertices = [V(x, y, z) for x, z in points]
    return Part.Face(Part.makePolygon(vertices + vertices[:1])).extrude(V(0, width, 0))


def validate(shape, expected=None):
    bounds = shape.optimalBoundingBox(False)
    size = [bounds.XLength, bounds.YLength, bounds.ZLength]
    assert shape.isValid() and shape.isClosed() and len(shape.Solids) == 1
    assert shape.Volume > 0 and all(v <= 256.0001 for v in size)
    if expected:
        assert all(abs(a - b) < 0.001 for a, b in zip(size, expected))
    return dict(size_mm=size, solids=len(shape.Solids), valid=shape.isValid(),
                closed=shape.isClosed(), volume_mm3=shape.Volume)


def make_plate():
    shape = box(0, 0, 0, LENGTH, WIDTH, PLATE)
    vertical = [e for e in shape.Edges if e.BoundBox.ZLength > PLATE - 0.01]
    shape = shape.makeFillet(8, vertical)
    rims = [e for e in shape.Edges if e.BoundBox.ZLength < 0.001]
    return shape.makeFillet(1, rims)


def make_clamp():
    inner = profile([(INNER-WALL, 1), (INNER, 1), (INNER, -DEPTH+3),
                     (INNER-0.6, -DEPTH), (INNER-WALL, -DEPTH)], 10, WIDTH-20)
    outer = profile([(OUTER, 1), (OUTER+WALL, 1), (OUTER+WALL, -DEPTH),
                     (OUTER+0.6, -DEPTH), (OUTER, -DEPTH+3)], 10, WIDTH-20)
    return (inner.makeFillet(0.6, inner.Edges), outer.makeFillet(0.6, outer.Edges))


def make_ribs():
    ribs = []
    for y in (12, WIDTH - 16):
        for points in (
            [(8, 1), (INNER-WALL+1, 1), (INNER-WALL+1, -RIB_DEPTH)],
            [(OUTER+WALL-1, 1), (LENGTH-8, 1), (OUTER+WALL-1, -RIB_DEPTH)],
        ):
            rib = profile(points, y, RIB_THICKNESS)
            ribs.append(rib.makeFillet(0.6, rib.Edges))
    assert len(ribs) == 4
    return ribs


def printable(shape):
    result = shape.copy()
    result.rotate(V(0, 0, 0), V(1, 0, 0), 180)
    bb = result.optimalBoundingBox(False)
    result.translate(V(-bb.XMin, -bb.YMin, -bb.ZMin))
    return result


def export_mesh(shape, filename):
    mesh = MeshPart.meshFromShape(Shape=printable(shape), LinearDeflection=0.08,
                                  AngularDeflection=0.15, Relative=False)
    assert mesh.isSolid(), 'STL must be watertight'
    mesh.write(str(ROOT / filename))
    return dict(facets=mesh.CountFacets, solid=mesh.isSolid())


def build():
    assert BOARD > 0 and 0 <= CLEARANCE <= 1 and DEPTH <= 120
    assert not (EXPORTS / f'bedside_shelf_{VERSION}.stl').exists(), 'Increase VERSION before exporting a changed model.'
    doc = App.getDocument('BedsideShelf') if 'BedsideShelf' in App.listDocuments() else App.newDocument('BedsideShelf')
    assert set(o.Name for o in doc.Objects) <= {'Shelf', 'BoardReference'}
    plate = make_plate()
    shape = plate
    inner, outer = make_clamp()
    shape = shape.fuse(inner).fuse(outer)
    ribs = make_ribs()
    for rib in ribs:
        shape = shape.fuse(rib)
    shape = shape.removeSplitter()
    report = {'shelf': validate(shape, [LENGTH, WIDTH, DEPTH + PLATE])}
    report['rib_count'] = len(ribs)
    report['rib_max_depth_mm'] = RIB_DEPTH
    for rib in ribs:
        assert shape.common(rib).Volume > rib.Volume - 0.001
        assert rib.optimalBoundingBox(False).ZMin >= -RIB_DEPTH - 0.001
    obj = doc.getObject('Shelf') or doc.addObject('PartDesign::Feature', 'Shelf')
    obj.Label = '床邊架 v3｜四片50mm淺支撐・圓角'
    obj.Shape = shape
    for name, value in [('BoardThickness', BOARD), ('RigidClearance', CLEARANCE),
                        ('ClampDepth', DEPTH), ('PlateThickness', PLATE), ('WallThickness', WALL)]:
        if name not in obj.PropertiesList:
            obj.addProperty('App::PropertyLength', name, 'Design')
        setattr(obj, name, value)
        obj.setEditorMode(name, 1)
    if 'SpringPreload' in obj.PropertiesList:
        obj.removeProperty('SpringPreload')
    if 'Rebuild' not in obj.PropertiesList:
        obj.addProperty('App::PropertyString', 'Rebuild', 'Design')
    obj.Rebuild = 'Edit build_shelf.py; properties are reference measurements.'
    obj.ViewObject.ShapeColor = (0.24, 0.52, 0.62)
    board_shape = box(INNER + CLEARANCE/2, 0, -120, BOARD, WIDTH, 120)
    board_obj = doc.getObject('BoardReference') or doc.addObject('PartDesign::Feature', 'BoardReference')
    board_obj.Label = '木板參考｜不列印'
    board_obj.Shape = board_shape
    board_obj.ViewObject.ShapeColor = (0.66, 0.45, 0.26)
    board_obj.ViewObject.Transparency = 65
    board_obj.ViewObject.Visibility = False
    overlap = shape.common(board_shape)
    assert overlap.Volume < 0.001
    report['board_interference_mm3'] = overlap.Volume
    report['rigid_gap_mm'] = OUTER - INNER
    report['shelf_mesh'] = export_mesh(shape, str(EXPORTS / f'bedside_shelf_{VERSION}.stl'))
    Part.export([obj], str(EXPORTS / f'bedside_shelf_{VERSION}.step'))
    doc.recompute()
    Gui.activeDocument().activeView().viewAxonometric()
    Gui.activeDocument().activeView().fitAll()
    doc.saveAs(str(MODELS / 'BedsideShelf.FCStd'))
    (REPORTS / f'validation_{VERSION}.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


build()
