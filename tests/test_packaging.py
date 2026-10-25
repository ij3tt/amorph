import os
import subprocess
import sys


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_gui_log_uses_utf8_with_legacy_standard_streams(tmp_path):
    package = tmp_path / "amorph_gui"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "__main__.py").write_text(
        "import sys\n\n"
        "def main():\n"
        "    print('Готово')\n"
        "    print('Тоже готово', file=sys.stderr)\n"
        "    return 0\n",
        encoding="utf-8")

    log = tmp_path / "self-test.log"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(tmp_path)
    env["PYTHONIOENCODING"] = "cp1252"
    env["AMORPH_GUI_LOG"] = str(log)
    subprocess.run([sys.executable,
                    os.path.join(ROOT, "packaging", "amorph_gui_app.py")],
                   check=True, env=env, capture_output=True)

    assert log.read_text(encoding="utf-8") == "Готово\nТоже готово\n"
