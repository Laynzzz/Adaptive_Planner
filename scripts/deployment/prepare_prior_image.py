"""Build the actual prior source image and a narrowly documented delivery bridge."""

import argparse
import io
import json
import shutil
import subprocess
import zipfile
from pathlib import Path
from uuid import uuid4

root = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument("--base-ref", required=True)
args = parser.parse_args()
revision = subprocess.check_output(["git", "rev-parse", args.base_ref], cwd=root, text=True).strip()
archive = subprocess.check_output(["git", "archive", "--format=zip", revision], cwd=root)
context = root / ".runtime" / ("prior-image-" + uuid4().hex)
context.mkdir(parents=True)
with zipfile.ZipFile(io.BytesIO(archive)) as files:
    for name in files.namelist():
        assert (context / name).resolve().is_relative_to(context.resolve())
    files.extractall(context)
for name in ("Dockerfile", ".dockerignore"):
    shutil.copy2(root / name, context / name)


def build(tag):
    subprocess.run(
        [
            "docker",
            "build",
            "--target",
            "runtime",
            "--build-arg",
            "REVISION=" + revision,
            "-t",
            tag,
            str(context),
        ],
        cwd=root,
        check=True,
    )


build("adaptive-planner:prior-unmodified")
source = context / "services/planner/src/planner"
shutil.copy2(
    root / "services/planner/src/planner/db/compatibility.py", source / "db/compatibility.py"
)
p = source / "db/session.py"
s = p.read_text()
start = s.index("    try:", s.index("def database_is_ready"))
end = s.index("\n\ndef migration_heads()", start)
s = (
    s[:start]
    + """    from planner.db.compatibility import compatible_schema
    return compatible_schema(engine, expected_heads)
"""
    + s[end:]
)
p.write_text(s)
p = source / "settings.py"
s = p.read_text().replace(
    "    session_hours: int = 8",
    "    session_hours: int = 8\n    static_dist_path: str | None = None",
)
p.write_text(s)
p = source / "app.py"
s = (
    p.read_text()
    .replace(
        "from fastapi.responses import JSONResponse",
        "from fastapi.responses import JSONResponse\nfrom fastapi.staticfiles import StaticFiles",
    )
    .replace(
        "    return app",
        "    if config.static_dist_path is not None:\n"
        '        app.mount("/", StaticFiles(directory=config.static_dist_path, html=True), '
        'name="web")\n'
        "    return app",
    )
)
p.write_text(s)
build("adaptive-planner:prior-bridge")
manifest = {
    "base_revision": revision,
    "context": str(context.relative_to(root)),
    "bridge_changes": [
        "db/compatibility.py additive exact-head reader policy",
        "db/session.py database_is_ready delegation",
        "settings.py optional static_dist_path",
        "app.py static frontend mount after routes",
    ],
    "unchanged": "R2 business, auth, worker and solver code",
}
(root / "docs/evidence/raw/task-18-prior-manifest.json").write_text(json.dumps(manifest, indent=2))
print(json.dumps(manifest))
