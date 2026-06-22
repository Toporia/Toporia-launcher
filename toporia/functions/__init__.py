# functions/__init__.py — catalogue of all selectable run modes
#
# Each name here is one mode that appears in the GUI's Mode dropdown.
# Import from here when you need programmatic access to multiple modes at once.
#
#   from toporia.functions import run_one, sweep, sensitivity_field, ...

from .Run_one          import run_one
from .sweep            import sweep
from .sweep_2d         import sweep_2d
from .Compare_Two      import compare_two
from .CompareLoadCases import compare_load_cases
from .Sensitivity      import sensitivity_field
from .SensitivitySweep import sensitivity_sweep, sensitivity_sweep_2d
