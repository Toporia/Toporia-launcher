# Contributing to Toporia

Thanks for your interest in contributing to Toporia. This project is meant to be open, collaborative, and easy to extend, so we welcome bug reports, documentation improvements, performance work, UI fixes, and new algorithms or plugins.

Toporia is licensed under the Apache 2.0 license, and contributions are expected to follow the same spirit: clear, testable, and respectful changes.

## Ways to contribute

You do not need to be a maintainer to help. Good contributions include:

- fixing bugs or edge cases
- improving the docs and examples
- adding or refining plugins, filters, models, or responses
- improving the browser UI or CLI experience
- adding tests for regressions or new behaviour
- benchmarking and validating performance
- reporting issues with reproduction steps

If you are planning a larger change, please open an issue or start a discussion first so the maintainers can help shape the scope and avoid duplicate work.

## Development setup

```bash
git clone https://github.com/Toporia/Toporia-launcher.git
cd Toporia-launcher
python -m venv .venv
# On Windows: .venv\Scripts\activate
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev,3d]"
```

This installs the project in editable mode with the recommended development and 3-D dependencies.

## Recommended workflow

1. Fork the repository and create a branch for your change.
2. Keep the scope focused: one issue, one fix, one set of related tests.
3. Read the relevant docs before changing architecture or plugin behaviour.
4. Add or update tests for the behaviour you changed.
5. Run the targeted checks before opening a pull request.
6. Open a pull request with a clear description of the problem and the fix.

## Writing and testing changes

For most changes, use the project test suite and static checks:

```bash
pytest
ruff check .
```

If you are adding a new method, filter, response, or plugin, also read the plugin guide in the docs before implementing it:

- `docs/quickstart.md`
- `docs/writing-plugins.md`
- `toporia/plugins/README.md`

For new plugin work, keep the code aligned with the existing architecture and document the mathematical or algorithmic intent clearly in the module docstring.

## Pull request expectations

A good pull request is easy to review and easy to understand. Please:

- use a clear title and summary
- explain the problem being solved
- include the motivation for the change
- link the relevant issue, if one exists
- include screenshots or examples for UI changes when helpful
- avoid mixing unrelated edits into the same PR
- keep generated files, local results, and editor metadata out of commits

If the change affects user-facing behaviour, include a brief note in the PR description about what changed and how it was validated.

## Reporting issues

When filing a bug report, include:

- a short description of the problem
- steps to reproduce it
- expected behaviour
- actual behaviour
- your environment (Python version, OS, install method)
- any relevant logs or screenshots

Please keep reports factual and actionable. Good bug reports help maintainers fix the root cause faster.

## Code quality and style

We aim for a straightforward, readable codebase. Please:

- prefer clear naming over clever shortcuts
- keep functions and modules focused
- document non-obvious design decisions
- do not add unrelated refactors to a bug fix
- keep tests deterministic and stable

If a change introduces new public behaviour, document it in the appropriate README or docs page.

## Community expectations

Please be respectful, constructive, and inclusive in issues, discussions, and pull requests. We welcome contributors from different backgrounds and experience levels.

If you are unsure whether a contribution is a good fit, ask first. It is always better to discuss an idea before spending time on a large implementation.

## License

By contributing to Toporia, you agree that your contributions will be licensed under the Apache 2.0 license.

Thank you for helping build a better and more transparent open-source topology optimisation toolkit.
