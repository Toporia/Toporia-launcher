# results.py — saving and plotting optimisation output
#
# ResultStore is created once per run.  The optimisation loop calls record()
# after every iteration, and save_final() when converged.
# It writes three types of files into the run's output folder:
#   density_NNNN.png   — greyscale density snapshot every save_every iterations
#   final_density.png  — the converged design
#   history.png        — objective and volume fraction plotted against iteration

import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image   # Python Imaging Library: used to write PNG files


class ResultStore:
    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)  # create folder if needed
        self.objectives = []   # compliance value recorded each iteration
        self.volumes    = []   # mean density (= material fraction) each iteration

    def record(self, iteration, objective, volume, density, save_every=0):
        """Append one iteration's data and optionally save a density snapshot."""
        self.objectives.append(float(objective))
        self.volumes.append(float(volume))
        # save_every=0 means disabled; otherwise save when iteration is a multiple
        if save_every and iteration % save_every == 0:
            self.save_density(density, self.output_dir / f"density_{iteration:04d}.png")

    def save_final(self, density, save_history=True):
        """Write the final density image, CSV, and optionally the history plot."""
        self.save_density(density, self.output_dir / "final_density.png")
        self.save_csv(density)
        if save_history:
            self.save_history()

    def save_csv(self, density):
        """Write final_density.csv: two metadata rows then the density matrix.

        Row 1 — iterations taken
        Row 2 — final objective value
        Rows 3+ — density matrix (row 0 = top of image, matching the PNG orientation)
        Each value is the material density [0, 1] of that finite element.
        """
        density_out = np.flipud(density)   # row 0 = image top, matching final_density.png
        with open(self.output_dir / "final_density.csv", "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["iterations", len(self.objectives)])
            writer.writerow(["objective",  f"{self.objectives[-1]:.6g}"])
            for row in density_out:
                writer.writerow([f"{v:.4f}" for v in row])

    def save_density(self, density, path):
        """Convert a float density array to an 8-bit greyscale PNG.

        Steps:
          1. flipud  — flip vertically so row 0 appears at the bottom of the image
          2. 1-density — invert so solid (density≈1) is dark and void (≈0) is light
          3. ×255    — scale to byte range [0, 255]
          4. clip    — guard against any values that slipped outside [0,1]
        """
        pixels = np.flipud(1.0 - density)
        pixels = (np.clip(pixels, 0.0, 1.0) * 255).astype(np.uint8)
        Image.fromarray(pixels, mode="L").save(path)   # "L" = 8-bit greyscale

    def save_history(self):
        """Write a two-panel PNG: objective (top) and volume fraction (bottom)."""
        fig, axes = plt.subplots(2, 1, figsize=(6, 5), sharex=True)  # shared x-axis
        axes[0].plot(self.objectives); axes[0].set_ylabel("Objective")
        axes[1].plot(self.volumes);    axes[1].set_ylabel("Volume")
        axes[1].set_xlabel("Iteration")
        fig.tight_layout()
        fig.savefig(self.output_dir / "history.png", dpi=160)
        plt.close(fig)   # close so the figure is not shown as an interactive window
