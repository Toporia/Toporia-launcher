"""test_postprocess.py — what is made of a finished design.

Post-processors are switched on in output.postprocess, in any combination;
they run after the optimisation, write into <run>/post, record their numbers
in run.json, add columns to a method comparison, and can be run again on a
saved run.  Each one is checked here on designs whose answer is known.
"""

import json
import struct

import numpy as np
import pytest

from toporia.engine.loop import initialized_method, run_single_with_store
from toporia.engine.pipeline import pipeline_stages
from toporia.engine.postprocess import postprocess_folder, run_postprocessors
from toporia.framework.parts.postprocess import PostProcessor, Result
from toporia.framework.problem.mesh import RectangularProblem
from toporia.plugins.postprocessors import POSTPROCESSORS
from toporia.plugins.postprocessors._measure import clip_to_box, outlines, polygon_area, referee_compliance
from toporia.plugins.postprocessors.export_dxf import ExportDXF
from toporia.plugins.postprocessors.export_stl import ExportSTL
from toporia.plugins.postprocessors.feature_size import thinnest
from toporia.plugins.postprocessors.threshold import Threshold
from toporia.plugins.problems import get_run

ALL = ["threshold", "connectivity", "feature_size", "export_svg", "export_dxf", "export_stl"]


def _run(name="MBB Beam", **values):
    return get_run(name).updated(**{"m": 0.5, "max_iter": 15, "tol": 0.0, "save_every": 0, **values})


def _result(design, tmp_path, name="MBB Beam", m=0.5):
    run = _run(name, m=m)
    problem = RectangularProblem(run.scenario, m)
    return Result(density=np.asarray(design, dtype=float), problem=problem, run=run, folder=tmp_path / "post")


def _shape(problem):
    return problem.nely, problem.nelx


def test_all_six_are_registered():
    assert POSTPROCESSORS.names() == ALL


# ── Threshold ─────────────────────────────────────────────────────────────────

def test_the_threshold_keeps_the_volume_and_the_holes(tmp_path):
    run = _run("Drone Arm", m=0.3)
    problem = RectangularProblem(run.scenario, 0.3)
    density = np.random.default_rng(0).uniform(0, 1, _shape(problem))
    result = Result(density=density, problem=problem, run=run, folder=tmp_path)
    metrics = Threshold().process(result)
    clipped = np.clip(density, problem.lower_bound, problem.upper_bound)
    assert abs(result.binary.sum() - clipped.sum()) <= 1.0                  # within one element
    assert set(np.unique(result.binary)) <= {0.0, 1.0}
    fixed = problem.upper_bound <= problem.lower_bound
    assert np.array_equal(result.binary[fixed], problem.lower_bound[fixed])  # holes and rings as given
    assert metrics["compliance"] == pytest.approx(referee_compliance(problem, result.binary))
    assert (tmp_path / "thresholded.png").exists()


def test_a_fixed_level_cuts_there(tmp_path):
    result = _result(np.full((10, 30), 0.4), tmp_path)
    assert Threshold(keep_volume=False, level=0.5).process(result)["volume"] == 0.0


# ── Connectivity ──────────────────────────────────────────────────────────────

def test_a_full_domain_is_one_supported_piece(tmp_path):
    result = _result(np.ones((10, 30)), tmp_path)
    metrics = POSTPROCESSORS.get("connectivity")().process(result)
    assert metrics == {"pieces": 1, "floating_fraction": 0.0, "loads_connected": True}


def test_an_island_floats_and_cuts_the_load_path(tmp_path):
    design = np.zeros((10, 30))
    design[4:6, 12:16] = 1.0                     # touches neither the supports nor the load
    metrics = POSTPROCESSORS.get("connectivity")().process(_result(design, tmp_path))
    assert metrics["pieces"] == 1 and metrics["floating_fraction"] == 1.0
    assert metrics["loads_connected"] is False


def test_elements_touching_only_at_a_corner_are_not_joined(tmp_path):
    design = np.zeros((10, 30))
    design[2, 2] = design[3, 3] = 1.0
    assert POSTPROCESSORS.get("connectivity")().process(_result(design, tmp_path))["pieces"] == 2


# ── Feature size ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("width, measured", [(1, 1), (3, 3), (4, 3), (5, 5), (7, 7)])
def test_the_thinnest_member_of_a_bar(width, measured):
    field = np.zeros((30, 40), dtype=bool)
    field[10:10 + width, 5:35] = True
    assert thinnest(np.pad(field, 1), np.ones((32, 42), dtype=bool)) == measured


def test_a_stepped_diagonal_is_measured_across_not_at_its_steps():
    field = np.zeros((40, 40), dtype=bool)
    for i in range(40):
        field[i, max(0, i - 2):i + 3] = True     # 5 wide horizontally: 3.5 across
    assert thinnest(np.pad(field, 1), np.ones((42, 42), dtype=bool)) == pytest.approx(3.47, abs=0.05)


# ── Exports ───────────────────────────────────────────────────────────────────

def _block(tmp_path, hole=False):
    design = np.zeros((10, 30))
    design[2:8, 5:25] = 1.0
    if hole:
        design[4:6, 10:16] = 0.0
    return _result(design, tmp_path)


@pytest.mark.parametrize("hole", [False, True])
def test_outlines_enclose_the_solid_area(tmp_path, hole):
    result = _block(tmp_path, hole)
    polygons = outlines(result)
    areas = sorted((abs(polygon_area(p)) for p in polygons), reverse=True)
    assert len(polygons) == (2 if hole else 1)
    solid_area = result.density.sum() * result.problem.dx * result.problem.dy
    enclosed = areas[0] - sum(areas[1:])
    assert enclosed == pytest.approx(solid_area, rel=0.08)       # corners are cut by the contour


def test_the_dxf_has_one_closed_polyline_per_outline(tmp_path):
    result = _block(tmp_path, hole=True)
    metrics = ExportDXF().process(result)
    text = (tmp_path / "post" / "design.dxf").read_text(encoding="ascii").split("\n")
    assert text.count("POLYLINE") == metrics["outlines"] == 2
    assert text[-2:] == ["EOF", ""] and "ENTITIES" in text


def test_the_stl_is_a_closed_solid_of_the_right_volume(tmp_path):
    result = _block(tmp_path, hole=True)
    ExportSTL(thickness=2.0).process(result)
    data = (tmp_path / "post" / "design.stl").read_bytes()
    count = struct.unpack("<I", data[80:84])[0]
    record = np.frombuffer(data[84:], dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("s", "<u2")])
    assert len(record) == count
    triangles = record["v"].astype(float)
    # Closed: every edge is shared by an even number of triangles.
    edges = {}
    for triangle in triangles:
        for a, b in ((0, 1), (1, 2), (2, 0)):
            key = tuple(sorted((tuple(triangle[a]), tuple(triangle[b]))))
            edges[key] = edges.get(key, 0) + 1
    assert all(n % 2 == 0 for n in edges.values())
    # Its volume, by the divergence theorem, is the solid area times the thickness.
    volume = np.sum(np.einsum("ij,ij->i", triangles[:, 0], np.cross(triangles[:, 1], triangles[:, 2]))) / 6
    solid_area = result.solid().sum() * result.problem.dx * result.problem.dy
    assert volume == pytest.approx(solid_area * 2.0, rel=1e-5)


def test_explicit_shapes_are_cut_to_the_domain():
    square = np.array([[-1, -1], [2, -1], [2, 2], [-1, 2], [-1, -1]], dtype=float)
    cut = clip_to_box(square, 1.0, 1.0)
    assert abs(polygon_area(cut)) == pytest.approx(1.0)
    assert clip_to_box(square + 10.0, 1.0, 1.0) is None          # wholly outside: nothing left


def test_moving_morphable_components_export_their_bars(tmp_path):
    run = _run(method="q4+mma", representation={"type": "mmc"}, method_params={"move": 0.02}, max_iter=3,
               postprocess=[{"type": "export_svg"}, {"type": "export_dxf", "source": "contour"}])
    store, _ = run_single_with_store(run.with_output_dir(tmp_path))
    assert store.postprocess["export_svg"]["metrics"]["from_geometry"] is True
    assert 0 < store.postprocess["export_svg"]["metrics"]["outlines"] <= 16      # bars outside the domain drop out
    assert 'fill-rule="nonzero"' in (tmp_path / "post" / "design.svg").read_text()
    assert store.postprocess["export_dxf"]["metrics"]["from_geometry"] is False
    assert len(json.loads((tmp_path / "final_geometry.json").read_text())["polygons"]) == 16


# ── In the engine ─────────────────────────────────────────────────────────────

def test_a_run_applies_them_in_order_and_records_them(tmp_path):
    run = _run(postprocess=[{"type": name} for name in ALL]).with_output_dir(tmp_path)
    assert dict(pipeline_stages(run))["Post-processing"].startswith("Threshold to black and white -> ")
    store, _ = run_single_with_store(run)
    record = json.loads((tmp_path / "run.json").read_text())
    assert list(record["postprocess"]) == ALL
    assert record["postprocess"]["threshold"]["files"] == ["post/thresholded.png", "post/thresholded.csv"]
    for entry in record["postprocess"].values():
        for name in entry["files"]:
            assert (tmp_path / name).exists()
    assert [p["kind"] for p in record["parts"]].count("postprocessor") == 6


def test_nothing_runs_when_none_is_switched_on(tmp_path):
    store, _ = run_single_with_store(_run(max_iter=2).with_output_dir(tmp_path))
    assert store.postprocess == {} and not (tmp_path / "post").exists()
    assert "postprocess" not in json.loads((tmp_path / "run.json").read_text())


def test_an_unknown_or_misconfigured_one_is_refused_before_the_run():
    with pytest.raises(ValueError, match="no_such_thing"):
        initialized_method(_run(postprocess=[{"type": "no_such_thing"}]))
    with pytest.raises(ValueError, match="thicknes"):
        initialized_method(_run(postprocess=[{"type": "export_stl", "thicknes": 3}]))


class _Broken(PostProcessor):
    name, label = "test_broken", "Broken"

    def process(self, result):
        raise RuntimeError("deliberately broken")


def test_one_that_fails_is_reported_and_the_rest_still_run(tmp_path, capsys):
    POSTPROCESSORS.register(_Broken)
    try:
        run = _run(postprocess=[{"type": "test_broken"}, {"type": "threshold"}])
        done = run_postprocessors(run, np.full((10, 30), 0.5), tmp_path)
    finally:
        POSTPROCESSORS.unregister(_Broken.name)
    assert "deliberately broken" in done["test_broken"]["error"]
    assert "compliance" in done["threshold"]["metrics"]
    assert "FAILED" in capsys.readouterr().out


def test_a_saved_run_can_be_post_processed_again(tmp_path):
    run = _run(postprocess=[{"type": "threshold"}]).with_output_dir(tmp_path)
    store, _ = run_single_with_store(run)
    again = postprocess_folder(tmp_path, [{"type": "threshold"}, {"type": "export_stl", "thickness": 1.0}])
    first = store.postprocess["threshold"]["metrics"]
    assert again["threshold"]["metrics"]["compliance"] == pytest.approx(first["compliance"], rel=1e-3)
    record = json.loads((tmp_path / "run.json").read_text())
    assert set(record["postprocess"]) == {"threshold", "export_stl"}
    assert (tmp_path / "post" / "design.stl").exists()


def test_compare_methods_gets_the_same_columns_for_every_method(tmp_path):
    from toporia.engine.modes.methods import compare_methods, format_table
    run = _run(m=0.3, max_iter=6, postprocess=[{"type": "threshold"}, {"type": "connectivity"},
                                               {"type": "export_svg"}]).with_output_dir(tmp_path)
    _, rows = compare_methods(["q4+oc", "q4+mma"], run)
    for row in rows:
        assert isinstance(row["threshold.compliance"], float) and "connectivity.pieces" in row
        assert not any(key.startswith("export_svg.") for key in row)     # files, not numbers to compare
    table = (tmp_path / "compare_methods" / "methods.csv").read_text(encoding="utf-8").splitlines()[0]
    assert "threshold.compliance" in table and "threshold.compliance" in format_table(rows)
