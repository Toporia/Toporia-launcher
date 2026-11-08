"""The GUI tests keep their preferences (appearance, recent projects) out of the user's own."""

import os
import tempfile
from pathlib import Path

os.environ["TOPORIA_SETTINGS"] = str(Path(tempfile.mkdtemp(prefix="toporia-test-settings-")) / "gui.ini")
