from pathlib import Path
import unittest
from unittest import mock
from scripts.autonomy import alignment_job, controller_return_job, event_pair_job, input_focus_job
from scripts.autonomy import poll_pair_job, update_job, scheduler


class OracleEffectDependencyTests(unittest.TestCase):
    def test_reader_change_reaches_each_direct_oracle_capture_identity(self):
        relative = 'scripts/phase9_oracle_instruction_effects.py'
        for module in (alignment_job, controller_return_job, event_pair_job, input_focus_job, poll_pair_job, update_job):
            with self.subTest(module=module.__name__):
                self.assertIn(relative, module.TOOL_FILES)
                function = getattr(module, 'tool_sha256', None) or module.alignment_tool_sha256
                with mock.patch.object(module, 'file_sha256', return_value='0'*64):
                    before = function(Path('.'))
                with mock.patch.object(module, 'file_sha256', side_effect=lambda path:
                        ('1' if path.as_posix() == relative else '0')*64):
                    after = function(Path('.'))
                self.assertNotEqual(before, after)
        self.assertIn(relative, scheduler.POLL_PAIR_PLAN_TOOLS)
