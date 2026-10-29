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

    def _add_function(self, kind, name):
        if self._running:
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
