"""Independent TOuNN-style coordinate MLP with explicit NumPy backpropagation.

Coordinates in [-1,1] pass through dense tanh hidden layers and a sigmoid
output. All weights and biases are design variables. Unlike the reference
PyTorch implementation, this smooth variant has no batch normalisation,
LeakyReLU, density offset, AMSGrad or built-in symmetry/manufacturing rules.
It uses the existing FE/filter/response chain and general-vector updaters.
No training dataset, pretrained weights or third-party neural code is used.
"""

import numpy as np
from scipy.special import expit, logit

from toporia.framework.params import Param
from toporia.framework.parts.representation import Representation


class NeuralField(Representation):
    """Mesh-independent parameter count; density sampled at element centres."""

    name = "neural"
    label = "Neural coordinate field (TOuNN-style)"
    order = 40
    dims = (2, 3)
    reference = (
        'Independent smooth coordinate-network variant inspired by A. Chandrasekhar and '
        'K. Suresh, "TOuNN: Topology Optimization using Neural Networks", SMO 63 (2021) '
        '1135-1149. Tanh hidden layers, sigmoid output and explicit NumPy backpropagation; '
        'not the original batch-normalised LeakyReLU/AMSGrad implementation. '
        'Papers: https://doi.org/10.1007/s00158-020-02748-4'
    )
    advice = (
        "Network weights are the variables. Use Adam with lr around 0.01 or MMA with "
        "a small move (around 0.005). Start with tol=0 and a bounded iteration budget. "
        "Neural fields can remain gray or get stuck; inspect volume and fine-grid physics."
    )
    params = (
        Param("width", 20, "Neurons per hidden layer", "Controls network capacity, not a certified feature size.",
              min=2, max=128),
        Param("depth", 2, "Hidden layers", "Number of dense tanh hidden layers.", min=1, max=5),
        Param("seed", 0, "Initialisation seed", "Local deterministic random generator; global RNG is unchanged.",
              min=0, max=1000000),
        Param("weight_bound", 8., "Weight/bias bound", "Symmetric finite bounds in network-weight units.",
              min=2., max=30., step=1., decimals=1),
    )

    def __init__(self, width=20, depth=2, seed=0, weight_bound=8.):
        for name, value, lower, upper in (("width", width, 2, 128), ("depth", depth, 1, 5),
                                          ("seed", seed, 0, 1000000)):
            if not np.isfinite(value) or int(value) != value or not lower <= value <= upper:
                raise ValueError(f"{name} must be an integer in [{lower}, {upper}]")
        if not np.isfinite(weight_bound) or not 2 <= weight_bound <= 30:
            raise ValueError("weight_bound must be finite and in [2, 30]")
        self.width, self.depth, self.seed = int(width), int(depth), int(seed)
        self.weight_bound = float(weight_bound)

    def setup(self, problem):
        self.problem = problem
        axes = [(problem.elem_x, problem.scenario.Lx), (problem.elem_y, problem.scenario.Ly)]
        if len(problem.shape) == 3:
            axes.append((problem.elem_z, problem.scenario.Lz))
        self.coordinates = np.column_stack([(2 * field / length - 1).ravel() for field, length in axes])
        sizes = [len(axes)] + [self.width] * self.depth + [1]
        self.shapes = [(a, b) for a, b in zip(sizes[:-1], sizes[1:], strict=True)]
        rng = np.random.default_rng(self.seed)
        values = []
        for layer, (a, b) in enumerate(self.shapes):
            # Zero output weights give exactly the requested uniform start.
            # Random hidden features still give distinct output-weight gradients.
            w = rng.normal(0, np.sqrt(2 / (a + b)), (a, b)) if layer < self.depth else np.zeros((a, b))
            bias = np.zeros(b)
            if layer == self.depth:
                volume = problem.scenario.volfrac
                if not expit(-self.weight_bound) < volume < expit(self.weight_bound):
                    raise ValueError("Initial volume requires a larger neural weight_bound")
                bias[:] = logit(volume)
            values.extend([w.ravel(), bias])
        self._start = np.concatenate(values)
        if np.max(np.abs(self._start)) > self.weight_bound:
            raise ValueError("Neural initialisation exceeds weight_bound; increase it or change seed")

    def initial(self):
        return self._start.copy()

    def bounds(self):
        return np.full_like(self._start, -self.weight_bound), np.full_like(self._start, self.weight_bound)

    def _forward(self, z):
        z = np.asarray(z)
        if z.shape != self._start.shape:
            raise ValueError(f"Expected {self._start.size} neural weights/biases")
        offset, layers, activations = 0, [], [self.coordinates]
        for index, (a, b) in enumerate(self.shapes):
            w = z[offset:offset + a * b].reshape(a, b)
            offset += a * b
            bias = z[offset:offset + b]
            offset += b
            value = activations[-1] @ w + bias
            activations.append(expit(value) if index == self.depth else np.tanh(value))
            layers.append(w)
        return layers, activations

    def density(self, z):
        return self._forward(z)[1][-1].reshape(self.problem.shape)

    def backward(self, z, sensitivity):
        layers, activations = self._forward(z)
        rho = activations[-1]
        delta = np.asarray(sensitivity).reshape(-1, 1) * rho * (1 - rho)
        gradients = []
        for index in reversed(range(len(layers))):
            gradients.append([(activations[index].T @ delta).ravel(), delta.sum(axis=0)])
            if index:
                delta = (delta @ layers[index].T) * (1 - activations[index] ** 2)
        return np.concatenate([part for gradient in reversed(gradients) for part in gradient])
