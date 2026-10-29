"""Coordinate local function networks with the existing generated parameter forms."""

from copy import deepcopy

from PySide6.QtWidgets import QMessageBox

from toporia.framework.problem.workflow import (
    nodes,
    optimization,
    stage_run,
    stage_settings,
    validate_workflow,
)


def _adapted(cfg, method_cls):
    """`cfg` as it is after switching to `method_cls`: an objective it computes, the constraints it enforces."""
    from dataclasses import replace
    caps = method_cls.capabilities
    scenario = cfg.scenario
    objective = scenario.objective
    if objective.get("type", "compliance") not in caps.objectives and caps.objectives:
        objective = {"type": caps.objectives[0]}
    constraints = [spec for spec in scenario.constraints if spec["type"] in caps.constraints]
    if caps.max_constraints is not None:
        constraints = constraints[:caps.max_constraints]
    return replace(cfg, scenario=replace(scenario, objective=objective, constraints=constraints))


class WorkflowActions:
    def _ensure_workflow(self):
        if not hasattr(self, "project"):
            return None
        if self.project.workflow is None:
            self.project.workflow = optimization("Optimization 1")
        tree = self.project.workflow
        stages = [node for node in nodes(tree) if node["kind"] == "optimization"]
        if getattr(self, "_active_stage", None) not in {node["id"] for node in stages}:
            saved = self.project.view.get("active_stage")
            self._active_stage = saved if saved in {node["id"] for node in stages} else stages[0]["id"]
        self.project.view["active_stage"] = self._active_stage
        return tree

    def _store_active_stage(self, cfg=None):
        tree = self._ensure_workflow()
        if tree is not None and not getattr(self, "_loading_stage", False):
            stage = next(node for node in nodes(tree) if node["id"] == self._active_stage)
            stage["settings"] = stage_settings(cfg or self.current_config())

    def _select_stage(self, key):
        tree = self._ensure_workflow()
        stage = next(node for node in nodes(tree) if node["id"] == key)
        self._store_active_stage()
        cfg = stage_run(self.current_config(), stage)
        self._active_stage = key
        self.project.view["active_stage"] = key
        self._loading_stage = True
        try:
            self._restore_inspector()
            self._populate_run(cfg)
        finally:
            self._loading_stage = False
        self._refresh_pipeline()

    def _library_offers(self, where):
        """Every registered part for `where` ("physics" or "loop"), as (label, kind, name, reason).

        The reason, empty when the part fits, says why it cannot be used with the
        current problem and the other selected parts; the library greys it out.
        """
        from toporia.framework.parts.composition import SEPARATOR, ComposedMethod
        from toporia.framework.registry import install_hint, missing_dependencies
        from toporia.plugins.interpolations import INTERPOLATIONS
        from toporia.plugins.methods import METHODS, method_class
        from toporia.plugins.models import MODELS
        from toporia.plugins.representations import REPRESENTATIONS
        from toporia.plugins.responses import CONSTRAINT_ROLE, OBJECTIVE_ROLE, responses_for
        from toporia.plugins.updaters import UPDATERS

        try:
            cfg = self.current_config()
            method = method_class(cfg.solver.method)
        except (ValueError, KeyError):
            return []
        composed = issubclass(method, ComposedMethod)
        caps = method.capabilities
        offers = []

        def add(prefix, kind, cls, reason="", current=False):
            missing = missing_dependencies(cls)
            if missing:
                reason = f"not installed: {install_hint(missing)}"
            offers.append((f"{prefix}: {cls.label}" + ("  (selected)" if current else ""), kind, cls.name, reason))

        def method_reason(name):
            from toporia.engine.pipeline import solver_problems
            try:
                candidate = method_class(name)
                dims = 3 if cfg.scenario.Lz else 2
                if dims not in candidate.capabilities.dims:
                    shown = " or ".join(f"{d}-D" for d in candidate.capabilities.dims)
                    return f"it works in {shown}; this problem is {dims}-D (Problem step, Dimensions)"
                if not candidate.capabilities.objectives:
                    return f"{candidate.label} has nothing it can minimise; choose another updater first"
                # Switching brings the candidate's own objective along (see _add_part).
                run = _adapted(cfg, candidate)
                reasons = candidate.capabilities.problems_with(run.scenario) or solver_problems(candidate, run)
            except (ValueError, KeyError) as error:
                reasons = [str(error)]
            return reasons[0] if reasons else ""

        updater = method.updater.name if composed else "mma"
        if where == "physics":
            for cls in MODELS.classes():
                add("Physics", "model", cls, method_reason(f"{cls.name}{SEPARATOR}{updater}"),
                    composed and cls is method.model)
            law = cfg.solver.interpolation.get("type", "simp")
            for cls in INTERPOLATIONS.classes():
                add("Material law", "interpolation", cls,
                    "" if caps.accepts_interpolation else f"{method.label} has its own material law",
                    caps.accepts_interpolation and cls.name == law)
            objective = cfg.scenario.objective.get("type", "compliance")
            for cls in responses_for(OBJECTIVE_ROLE):
                add("Objective", "objective", cls,
                    "" if cls.name in caps.objectives else f"{method.label} does not compute it",
                    cls.name == objective)
            for cls in responses_for(CONSTRAINT_ROLE):
                reason = ("" if cls.name in caps.constraints and caps.max_constraints != 0
                          else f"{method.label} cannot enforce it")
                add("+ Constraint", "constraint", cls, reason)
            return offers
        if composed:
            for cls in UPDATERS.classes():
                add("Updater", "updater", cls, method_reason(f"{method.model.name}{SEPARATOR}{cls.name}"),
                    cls is method.updater)
        for cls in METHODS.classes():
            add("Whole method", "method", cls, method_reason(cls.name), cls is method)
        representation = cfg.solver.representation.get("type", "element_density")
        for cls in REPRESENTATIONS.classes():
            add("Representation", "representation", cls,
                "" if caps.accepts_representation else f"{method.label} brings its own design representation",
                caps.accepts_representation and cls.name == representation)
        return offers

    def _add_part(self, kind, name):
        """Use the library's part `name` in the selected optimisation stage."""
        from toporia.framework.parts.composition import SEPARATOR, ComposedMethod
        from toporia.plugins.methods import method_class

        method = method_class(self.core.method_name())
        composed = issubclass(method, ComposedMethod)
        if kind in {"model", "updater", "method"}:
            chosen = {"model": f"{name}{SEPARATOR}{method.updater.name if composed else 'mma'}",
                      "updater": f"{method.model.name}{SEPARATOR}{name}" if composed else name,
                      "method": name}[kind]
            self.core.select_method(chosen)
            adapted = _adapted(self.current_config(), method_class(chosen)).scenario
            self.objective.load_spec(adapted.objective)
            self.constraints.load_specs(adapted.constraints)
        elif kind == "interpolation":
            self.material.load_spec({"type": name})
        elif kind == "objective":
            self.objective.load_spec({"type": name})
        elif kind == "constraint":
            self.constraints.load_specs([*self.constraints.get_specs(), {"type": name}])
        elif kind == "representation":
            self.design.load_spec({"type": name})
        self._on_method_changed(self.core.method_name())
        self.method_view._signature = None
        self._refresh_pipeline()

    def _add_function(self, kind, name):
        if self._running:
            return
        if kind in {"model", "updater", "method", "interpolation", "objective", "constraint", "representation"}:
            self._add_part(kind, name)
            return
        if kind == "navigate":
            self.method_view.enter(name)
            return
        if kind == "inspect":
            from toporia.engine.pipeline import GraphNode
            self._inspect_method_node(GraphNode(name, name.capitalize(), "Optional computation settings"))
            return
        if kind == "filter":
            from toporia.framework.registry import missing_dependencies
            from toporia.plugins.filters import FILTERS
            if missing_dependencies(FILTERS.get(name)):
                QMessageBox.information(self, "Unavailable function", "This filter requires optional dependencies. See its Function Explorer entry.")
                return
            self.filters.load_specs([*self.filters.get_specs(), {"type": name}])
            return
        tree = self._ensure_workflow()
        self._store_active_stage()
        changed = deepcopy(tree)
        context = self.method_view.context.split("/")[0]
        parent = next((node for node in nodes(changed) if node["id"] == context), changed)
        if kind == "operation":
            if parent["kind"] == "parallel":
                parent["operation"] = name
        elif kind == "composition":
            created = []
            def fresh():
                node = optimization(f"Optimization {sum(n['kind'] == 'optimization' for n in nodes(changed)) + len(created) + 1}")
                node["settings"] = stage_settings(self.current_config())
                created.append(node)
                return node

            if context == "root":
                new = optimization(name.capitalize())
                new["kind"] = name
                new["children"] = [changed, fresh()]
                if name == "parallel":
                    new["operation"] = "union"
                changed = new
            elif parent["kind"] in {"sequential", "parallel"}:
                child = fresh()
                if name != "optimization":
                    child = {**optimization(name.capitalize()), "kind": name,
                             "children": [child, fresh()]}
                    if name == "parallel":
                        child["operation"] = "union"
                parent["children"].append(child)
            else:
                return
        else:
            return
        try:
            validate_workflow(changed)
        except ValueError as error:
            QMessageBox.warning(self, "Cannot add function", str(error))
            return
        self.project.workflow = changed
        self.method_view._signature = None
        self._refresh_pipeline()

    def _workflow_preflight(self, cfg):
        from toporia.engine.workflow import execution_problems

        from .preflight import problems
        tree = self._ensure_workflow()
        validate_workflow(tree)
        issues = execution_problems(cfg, tree)
        for node in nodes(tree):
            if node["kind"] == "optimization":
                for issue in problems(stage_run(cfg, node), check_mesh=True, mesh_limit=None):
                    issues.append(f"{node['name']}: {issue}")
        return issues
