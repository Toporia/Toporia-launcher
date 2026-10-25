"""Own force-inverter example in the spirit of Sigmund's mechanism formulation."""

from toporia.framework import LoadCase, PointConstraint, PointLoad, PointSpring, Scenario, Solver

NAME = "Force Inverter"
ORDER = 85
ABOUT = ("A square mechanism held at the two left corners: a rightward input force "
         "should move the right output port leftward. Ground springs represent both ports.")
REFERENCE = (
    'O. Sigmund, "On the Design of Compliant Mechanisms Using Topology Optimization", '
    'Mechanics of Structures and Machines 25 (1997) 493-524. '
    'Toporia uses its own dimensions and spring/load values, not a paper replication. '
    'Papers: https://doi.org/10.1080/08905459708945415'
)


def scenario():
    return Scenario(
        Lx=40.0, Ly=40.0, volfrac=0.4,
        point_constraints=[PointConstraint(0.0, 0.0), PointConstraint(0.0, 40.0)],
        point_loads=[PointLoad(0.0, 20.0)],
        load_cases=[LoadCase(Fmag=0.001, Fa=0.0)],
        point_springs=[PointSpring(0.0, 20.0, 0.01), PointSpring(40.0, 20.0, 0.01)],
        objective={"type": "output_displacement", "x": 40.0, "y": 20.0, "angle": 180.0},
    )


def solver():
    return Solver(method="q4_mechanism+mma", m=1.0, max_iter=200, tol=0.001,
                  method_params={"move": 0.1}, filter_specs=[{"type": "density", "rmin": 1.5}])
