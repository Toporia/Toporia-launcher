"""apps/gui/panels — every input panel of the main window, one module each.

None of them contains optimisation logic.  Method, filter, response and
scenario inputs are not written by hand: each is a ParamForm (forms.py)
generated from the Param declarations of the plugins and of
framework/problem, so a new plugin or parameter appears without editing here.

What contains what, top to bottom in the left panel:

    PipelineView        pipeline.py   the selected chain, and why any part is unavailable
    CoreParamsGroup     method.py     mesh, volume; physics model + updater, or a whole method
    RepresentationGroup specs.py      what the design variables are (element densities, MMC)
    MaterialGroup       specs.py      the material law (SIMP, RAMP), when the method takes one
    ObjectiveGroup      specs.py      what to minimise, as the method allows
    SpecListGroup       specs.py      constraints (hidden when the method enforces none)
    SpecListGroup       specs.py      filters (hidden when the method takes no filters)
    ScheduleListGroup   specs.py      continuation: parameters that change during the run
    VariantsGroup       variants.py   several versions of every design (robust design)
    LoadCasesGroup      loads.py      one LoadCaseRow per force
    one group per mode  modes.py      sweep, compare, sensitivity, ...
"""

from .forms import ParamForm
from .loads import LoadCaseRow, LoadCasesGroup
from .method import CoreParamsGroup
from .modes import (
    CompareLoadCasesParamsGroup,
    CompareMethodsParamsGroup,
    CompareTwoParamsGroup,
    SensitivityParamsGroup,
    SensitivitySweep2DParamsGroup,
    SensitivitySweepParamsGroup,
    Sweep2DParamsGroup,
    SweepParamsGroup,
)
from .pipeline import PipelineView
from .specs import MaterialGroup, ObjectiveGroup, RepresentationGroup, ScheduleListGroup, SpecListGroup
from .variants import VariantsGroup

__all__ = [
    "ParamForm", "LoadCaseRow", "LoadCasesGroup", "CoreParamsGroup", "PipelineView",
    "ObjectiveGroup", "MaterialGroup", "RepresentationGroup", "ScheduleListGroup", "SpecListGroup", "VariantsGroup", "CompareLoadCasesParamsGroup", "CompareMethodsParamsGroup",
    "CompareTwoParamsGroup",
    "SensitivityParamsGroup", "SensitivitySweepParamsGroup", "SensitivitySweep2DParamsGroup",
    "SweepParamsGroup", "Sweep2DParamsGroup",
]
