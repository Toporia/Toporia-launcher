# apps/gui/config.py — turn the widgets' values into a Run.
#
# Kept apart from runner.py, which imports every optimisation routine: the
# window rebuilds the Run whenever a selection changes, to show the pipeline
# it describes, and that must stay cheap.


def build_config(core, lc, filters=None, base_cfg=None, objective=None, constraints=None, interpolation=None,
                 representation=None, schedules=None, variants=None,
                 postprocess=None):
    """Read widget values and overlay them on a Run.

    core     — CoreParamsGroup widget (scenario fields, method and its parameters)
    lc       — LoadCasesGroup widget (list of LoadCase objects)
    filters     — SpecListGroup of filters (optional)
    objective   — ObjectiveGroup (optional)
    constraints — SpecListGroup of constraints (optional)
    interpolation — MaterialGroup, the material law (optional)
    representation — RepresentationGroup, what the design variables are (optional)
    schedules — ScheduleListGroup, the continuation schedules (optional)
    variants — VariantsGroup, several versions of every design (optional)
    postprocess — SpecListGroup of post-processors, applied to the final design (optional)
    base_cfg — Run from the selected preset; provides everything the widgets do
               not expose (geometry, supports, material).  Falls back to the
               default preset if None.

    Each widget value is written with apply_param, so it lands in the Scenario,
    the Solver or the Output according to which of them owns that field.
    """
    if base_cfg is None:
        from toporia.plugins.problems import get_default_run
        base_cfg = get_default_run()
    values = {**core.get_kwargs(), "load_cases": lc.get_load_cases()}
    if filters is not None:
        values["filter_specs"] = filters.get_specs()
    if objective is not None:
        values["objective"] = objective.get_spec()
    if constraints is not None:
        values["constraints"] = constraints.get_specs()
    if interpolation is not None:
        values["interpolation"] = interpolation.get_spec()
    if representation is not None:
        values["representation"] = representation.get_spec()
    if schedules is not None:
        values["schedules"] = schedules.get_specs()
    if variants is not None:
        values["variants"] = variants.get_spec()
    if postprocess is not None:
        values["postprocess"] = postprocess.get_specs()
    return base_cfg.updated(**values)
