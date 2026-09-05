"""Exercise the shipped ZIP in an isolated credential directory without uploads."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

root = Path(__file__).resolve().parents[1]
version = (root / "plugins/cine-sleuth/skills/cine-sleuth/VERSION").read_text().strip()
with tempfile.TemporaryDirectory(prefix="cine-clean-install-") as directory:
    temporary = Path(directory)
    with zipfile.ZipFile(root / f"dist/cine-sleuth-workbuddy-{version}.zip") as archive:
        archive.extractall(temporary)
    skill = temporary / "cine-sleuth"
    env = dict(os.environ, LOCALAPPDATA=str(temporary / "credentials"),
               XDG_CONFIG_HOME=str(temporary / "credentials"), PYTHONUTF8="1")
    env.pop("LYCHEE_LAB_TOKEN", None)
    result = subprocess.run([sys.executable, str(skill / "scripts/doctor.py")],
                            env=env, capture_output=True, text=True, check=True)
    doctor = json.loads(result.stdout)
    assert doctor["version"] == version and doctor["installed"]
    assert not doctor["authenticated"] and not doctor["runtime_ready"]
    assert doctor["mode"] == "no-spend"
    for script in ("prepare_video_source.py", "build_visual_report.py"):
        subprocess.run([sys.executable, str(skill / "scripts" / script), "--help"],
                       env=env, capture_output=True, check=True)
    print(json.dumps({"clean_install": "passed", "doctor": doctor}))
