# `toporia/apps` — the browser app and command line

The browser app and CLI contain no optimization logic. They turn what the person chose into a
[`Run`](../framework/problem/run.py) and hand it to the [`engine`](../engine/README.md).

```
apps/
├── cli.py            the command line; with no command, the browser UI
└── web/              local Flask server and browser UI
    ├── __init__.py   API, local job runner, and server launch
    ├── templates/    the page
    └── static/       browser interactions and styling
```

`toporia` (or `toporia web`) starts the browser UI at `http://127.0.0.1:8765/`. It binds to
loopback only and accepts one optimization job at a time. Stop the server with Ctrl+C in
the terminal. Runs and files are stored under `results/web/`.

The browser reconnects to the current job after a page refresh while the server is running.
Job state lives in server memory, so stopping or restarting the server interrupts active jobs;
completed result files remain in `results/web/`.

The Compose setup binds the server on the container interface while publishing it only to
the host's loopback address. It mounts `results/web/` so output files remain available on
the host.

The browser app is a local front end over the existing optimization engine. It builds and
validates `Run` configurations, sends them to engine modes, and presents progress and results.
The CLI can invoke the same engine directly without starting the browser or a web server.
The framework, plugins, and engine do not depend on the browser app.

Both interfaces generate plugin parameter forms from the same `Param` declarations. The
browser exposes the pipeline, design, material, objective, constraint, filter, schedule,
variant, load-case, output, and analysis-mode controls; its pipeline description uses the
engine's shared pipeline code. Advanced JSON remains available for preset geometry and
expert-only fields. Methods and plugins whose optional packages are missing are identified
before a run.
