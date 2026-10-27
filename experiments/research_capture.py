"""Capture the unchanged author top82 paper reference with temporary preferences.

python -m experiments.research_capture --source-dir PATH --matlab-exe PATH
Downloads/installs nothing. Writes a fresh capture under results/, never changes
a stored test fixture or golden baseline. Review a capture before promoting it.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

SOURCE_HASH = "3e2fc7e86e21087dc8c84b616feb3a35a7eb7379ae58beff3a216d51556201da"


def capture(source_dir, executable, output):
    source = Path(source_dir) / "top82.m"
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest != SOURCE_HASH:
        raise ValueError("Author top82.m hash differs from the reviewed source; MATLAB was not started")
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="toporia-top82-", dir=output) as temporary:
        scratch = Path(temporary)
        shutil.copyfile(source, scratch / "top82.m")
        (scratch / "prefs").mkdir()
        script = r"""set(groot,'defaultFigureVisible','off');
report.runtime=version; report.command='top82(150,50,0.5,3,6,2)';
output=evalc(report.command);
tokens=regexp(output,'It.:\s*(\d+)\s+Obj.:\s*([\d.eE+-]+)\s+Vol.:\s*([\d.eE+-]+)\s+ch.:\s*([\d.eE+-]+)','tokens');
assert(~isempty(tokens),'No iteration trace');
image=findobj(gcf,'Type','image'); assert(numel(image)==1,'Unexpected author figure');
report.density=1-get(image,'CData'); report.iterations=numel(tokens);
report.history=zeros(numel(tokens),4);
for j=1:numel(tokens), report.history(j,:)=cellfun(@str2double,tokens{j}); end
fid=fopen('capture.json','w'); fprintf(fid,'%s',jsonencode(report)); fclose(fid); close all force;
"""
        (scratch / "capture.m").write_text(script, encoding="utf-8")
        process = subprocess.run([str(executable), "-batch", "run('capture.m');"], cwd=scratch,
                                 env={**os.environ, "MATLAB_PREFDIR": str(scratch / "prefs")},
                                 capture_output=True, text=True, timeout=1200, check=False)
        if process.returncode:
            raise RuntimeError("Author capture failed:\n" + process.stdout + "\n" + process.stderr)
        report = json.loads((scratch / "capture.json").read_text(encoding="utf-8"))
    report.update(source_sha256=digest, captured_at=datetime.now(timezone.utc).isoformat(),
                  source_url="https://www.topopt.mek.dtu.dk/-/media/subsites/topopt/apps/dokumenter-og-filer-til-apps/top82.m",
                  target="Andreassen Figure 4(b), density PDE panel, 150x50 cells, radius 6",
                  density_order="Author image top-down; flip once for physical-y comparison",
                  protocol="Unchanged author source; temporary preferences; printed compliance is pre-update.")
    destination = output / "top82-original-capture.json"
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--matlab-exe", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "results/research/batch2/capture")
    args = parser.parse_args()
    print(capture(args.source_dir, args.matlab_exe, args.output))
