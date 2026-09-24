import json
import subprocess
import sys
from pathlib import Path


def test_smoke_without_console_streams(tmp_path):
    import os
    env = {**os.environ, 'CUA_LAB_DATA_DIR': str(tmp_path)}
    result = subprocess.run(
        [sys.executable, '-c', "import sys, main; sys.stdout=None; sys.stderr=None; sys.argv=['main.py','--smoke-test']; raise SystemExit(main.main())"],
        cwd=Path(__file__).resolve().parents[1], env=env, timeout=30,
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    report=json.loads((tmp_path/'smoke-test.json').read_text())
    assert report['status'] == 'passed'
    assert {'backend','static_resources'} <= set(report['checks'])


def test_startup_failure_logged_without_credentials(tmp_path, monkeypatch):
    from main import report_startup_failure
    monkeypatch.setenv('CUA_LAB_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('OPENROUTER_API_KEY', 'private-test-key')
    report_startup_failure(RuntimeError('failure private-test-key'), interactive=False)
    log = (tmp_path/'logs/startup.log').read_text()
    assert 'RuntimeError' in log and '[REDACTED]' in log
    assert 'private-test-key' not in log
