"""Domain-organized test suites with stable shared-fixture imports."""
from pathlib import Path
_root = Path(__file__).resolve().parent
__path__ = [str(_root)] + [str(_root / name) for name in ['frontend', 'testkernel', 'autonomy', 'boot', 'build', 'diagnostics', 'evidence', 'exploration', 'platform', 'release', 'renderer', 'runtime', 'validation', 'verification']]
