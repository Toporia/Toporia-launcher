import base64
import io
import json
import threading
import time

import numpy as np
import pytest
from PIL import Image

from toporia.apps import web


def test_browser_page_and_metadata_are_served(tmp_path):
    client = web.create_app(tmp_path).test_client()

    page = client.get("/")
    metadata = client.get("/api/metadata")

    assert page.status_code == 200
    assert b"Toporia" in page.data
    assert metadata.status_code == 200
    body = metadata.get_json()
    assert {mode["id"] for mode in body["modes"]} == set(web.MODES)
    assert "MBB Beam" in {preset["name"] for preset in body["presets"]}
    method = next(item for item in body["methods"] if item["name"] == "q4+oc")
    assert method["composed"]
    assert method["model"] == "q4"
    assert method["updater"] == "oc"
    assert "move" in {param["name"] for param in method["params"]}
    assert {"filters", "interpolations", "representations", "objectives", "constraints",
            "schedules", "postprocessors", "models", "updaters", "params"} <= set(body)
    assert next(item for item in body["models"] if item["name"] == "q4")["capabilities"]["dims"] == [2]


def test_pipeline_description_returns_live_stages_and_sweep_paths(tmp_path):
    client = web.create_app(tmp_path).test_client()
    preset = next(item for item in client.get("/api/metadata").get_json()["presets"]
                  if item["name"] == "MBB Beam")

    response = client.post("/api/describe", json={
        "preset": preset["name"],
        "scenario": preset["scenario"],
        "solver": preset["solver"],
        "output": preset["output"],
    })

    assert response.status_code == 200
    result = response.get_json()
    stages = {stage for stage, _ in result["stages"]}
    assert {"Design", "Filters", "Physics", "Material", "Objective", "Updater"} <= stages
    paths = {item["path"] for item in result["parameters"]}
    assert {"volfrac", "m", "method.move"} <= paths
    assert any(path.startswith("filters[0].") for path in paths)


def test_pipeline_description_rejects_non_object_payload(tmp_path):
    client = web.create_app(tmp_path).test_client()

    response = client.post("/api/describe", json=[])

    assert response.status_code == 400
    assert response.get_json()["error"] == "The request body must be a JSON object."


def test_default_cli_command_launches_browser_ui(monkeypatch):
    from toporia.apps import cli, web

    launched = []
    monkeypatch.setattr(web, "launch", lambda: launched.append(True))

    assert cli.main([]) == 0
    assert launched == [True]


def test_launch_supports_container_binding_without_opening_a_browser(monkeypatch, capsys):
    from toporia.apps import web

    calls = {}

    class Server:
        def serve_forever(self):
            calls["served"] = True

    def make_server(host, port, app, threaded):
        calls["server"] = (host, port, threaded)
        return Server()

    monkeypatch.setattr("werkzeug.serving.make_server", make_server)
    monkeypatch.setattr(web, "create_app", lambda: object())
    monkeypatch.setattr(web.webbrowser, "open_new_tab", lambda _: pytest.fail("browser should not open"))
    monkeypatch.setenv("TOPORIA_WEB_HOST", "0.0.0.0")
    monkeypatch.setenv("TOPORIA_WEB_PORT", "8765")
    monkeypatch.setenv("TOPORIA_WEB_OPEN_BROWSER", "0")

    web.launch()

    assert calls["server"] == ("0.0.0.0", 8765, True)
    assert calls["served"]
    assert "http://127.0.0.1:8765/" in capsys.readouterr().out


def test_job_progress_results_and_safe_downloads(tmp_path, monkeypatch):
    completed = threading.Event()

    def fake_dispatch(run, mode, options, on_iteration):
        on_iteration(np.array([[1.0, 0.0], [0.0, 1.0]]), [4.0, 3.0], 2)
        artifact = run.output.dir / "answer.json"
        artifact.write_text(json.dumps({"ok": True}), encoding="utf-8")
        completed.set()
        return artifact

    monkeypatch.setattr(web, "_dispatch", fake_dispatch)
    client = web.create_app(tmp_path).test_client()
    response = client.post("/api/jobs", json={"preset": "MBB Beam", "mode": "run_one"})

    assert response.status_code == 202
    job_id = response.get_json()["id"]
    assert completed.wait(3)
    deadline = time.monotonic() + 3
    job = client.get(f"/api/jobs/{job_id}").get_json()
    while job["status"] in {"queued", "running"} and time.monotonic() < deadline:
        time.sleep(0.01)
        job = client.get(f"/api/jobs/{job_id}").get_json()
    assert job["status"] == "completed"
    assert job["iteration"] == 2
    assert job["objectives"] == [4.0, 3.0]
    assert job["density_png"]
    pixels = np.asarray(Image.open(io.BytesIO(base64.b64decode(job["density_png"]))))
    assert pixels.shape == (2, 2, 4)
    assert pixels[..., 3].tolist() == [[0, 255], [255, 0]]
    assert pixels[0, 1, :3].tolist() == [207, 207, 200]
    assert "answer.json" in job["artifacts"]
    assert client.get(f"/api/jobs/{job_id}/files/answer.json").status_code == 200
    assert client.get(f"/api/jobs/{job_id}/files/%2E%2E%2Fsecret.json").status_code == 404


def test_invalid_mode_options_are_reported_without_starting_a_job(tmp_path):
    client = web.create_app(tmp_path).test_client()

    response = client.post("/api/jobs", json={
        "preset": "MBB Beam",
        "mode": "sweep",
        "options": {"parameter": "../../outside"},
    })

    assert response.status_code == 400
    assert "missing" in response.get_json()["error"]


def test_only_one_job_can_run_at_a_time(tmp_path, monkeypatch):
    started = threading.Event()
    finish = threading.Event()

    def blocked_dispatch(run, mode, options, on_iteration):
        started.set()
        finish.wait(3)
        return None

    monkeypatch.setattr(web, "_dispatch", blocked_dispatch)
    client = web.create_app(tmp_path).test_client()
    payload = {"preset": "MBB Beam", "mode": "run_one"}

    first = client.post("/api/jobs", json=payload)
    assert first.status_code == 202
    assert started.wait(3)
    second = client.post("/api/jobs", json=payload)
    finish.set()

    assert second.status_code == 409


def test_browser_job_runs_one_iteration_and_saves_results(tmp_path):
    client = web.create_app(tmp_path).test_client()
    preset = next(item for item in client.get("/api/metadata").get_json()["presets"]
                  if item["name"] == "MBB Beam")
    preset["scenario"]["volfrac"] = 0.3
    preset["solver"]["m"] = 0.2
    preset["solver"]["max_iter"] = 1
    response = client.post("/api/jobs", json={
        "preset": "MBB Beam",
        "mode": "run_one",
        "scenario": preset["scenario"],
        "solver": preset["solver"],
        "output": preset["output"],
    })
    assert response.status_code == 202
    job_id = response.get_json()["id"]

    deadline = time.monotonic() + 30
    job = client.get(f"/api/jobs/{job_id}").get_json()
    while job["status"] in {"queued", "running"} and time.monotonic() < deadline:
        time.sleep(0.05)
        job = client.get(f"/api/jobs/{job_id}").get_json()

    assert job["status"] == "completed", job["error"]
    assert job["iteration"] == job["total_iterations"] == 1
    assert "final_density.png" in job["artifacts"]
