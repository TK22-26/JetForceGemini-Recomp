from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock
from scripts.release import release_metadata as release

class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'launcher/windows').mkdir(parents=True)
        self.version('1.0.0')
        (self.root / 'CMakeLists.txt').write_text('project( jfg_recomp VERSION 1.0.0 LANGUAGES C CXX)', encoding='utf-8')
        self.metadata = {'tag': 'v1.0.0', 'version': '1.0.0', 'commit': 'a' * 40, 'prerelease': False}

    def version(self, version):
        (self.root / 'launcher/windows/Launcher.cs').write_text(
            f'[assembly: AssemblyInformationalVersion("{version}")]', encoding='utf-8')

    def test_package_version_follows_source(self):
        self.version('1.2.3-rc.1')
        self.assertEqual(release.launcher_version(self.root), '1.2.3-rc.1')

    def test_invalid_versions_rejected(self):
        for version in ('01.0.0', '1.0', '1.0.0/evil', '1.0.0-rc.01', ''):
            with self.subTest(version=version):
                self.version(version)
                with self.assertRaises(ValueError):
                    release.launcher_version(self.root)

    def test_stable_tag_on_main(self):
        with mock.patch.object(release, 'command', side_effect=['a' * 40, 'a' * 40]), mock.patch.object(release.subprocess, 'run') as git:
            self.assertEqual(release.release_metadata(self.root, 'v1.0.0', 'tag'), self.metadata)
            self.assertIn('origin/main', git.call_args.args[0])

    def test_preview_tag_classified_separately(self):
        self.version('1.0.0-rc.1')
        with mock.patch.object(release, 'command', side_effect=['a' * 40, 'a' * 40]), mock.patch.object(release.subprocess, 'run'):
            self.assertTrue(release.release_metadata(self.root, 'v1.0.0-rc.1', 'tag')['prerelease'])

    def test_branches_and_mismatched_tags_rejected(self):
        for tag, ref in [('main', 'branch'), ('v0.4.0-preview.4', 'tag'), ('v1.0', 'tag')]:
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                release.release_metadata(self.root, tag, ref)

    def test_mismatched_cmake_version_rejected(self):
        (self.root / 'CMakeLists.txt').write_text('project(jfg_recomp VERSION 2.0.0)', encoding='utf-8')
        with self.assertRaises(ValueError):
            release.release_metadata(self.root, 'v1.0.0', 'tag')

    def test_moved_tag_rejected(self):
        with mock.patch.object(release, 'command', side_effect=['a' * 40, 'b' * 40]), self.assertRaises(ValueError):
            release.release_metadata(self.root, 'v1.0.0', 'tag')

    def test_commit_outside_main_rejected(self):
        with mock.patch.object(release, 'command', side_effect=['a' * 40, 'a' * 40]), mock.patch.object(release.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, ['git'])), self.assertRaises(subprocess.CalledProcessError):
            release.release_metadata(self.root, 'v1.0.0', 'tag')


if __name__ == "__main__":
    unittest.main()
