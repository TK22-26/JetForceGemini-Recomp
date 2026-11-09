import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile
from scripts import package_beta as package
from scripts import release_prebuilt as release
from scripts import program_bundle
from tests.build.test_program_bundle import identity

class PrebuiltReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); runtime = self.root / 'runtime'; runtime.mkdir()
        launcher = self.root / 'launcher.exe'; launcher.write_bytes(b'MZsynthetic-launcher')
        for name in package.RUNTIME_FILES: (runtime / name).write_bytes(b'MZsynthetic-runtime')
        (runtime / 'jfg-native-boot.exe.support').write_text('build_dirty=0\nbuild_source=fixture\nbuild_runtime_sha256=' + package.digest(runtime / 'jfg-native-boot.exe') + '\n')
        self.write_manifest(runtime, 'us')
        self.describe = self.enterContext(mock.patch.object(program_bundle, 'describe', side_effect=lambda path: json.loads((path.parent / program_bundle.MANIFEST_NAME).read_text(encoding='utf-8'))['identity']))
        self.version = '1.1.0-beta.1'
        self.archive = package.package(launcher, runtime, self.root / 'bundle', self.version)
        self.inventory_path = self.archive.with_suffix('.inventory.json')
        self.inventory = json.loads(self.inventory_path.read_text())
        self.metadata = {'version': self.version, 'commit': self.inventory['launcher_source']}
        self.runtime = runtime; self.launcher = launcher

    def write_manifest(self, runtime, code):
        value = dict(schema_version=1, kind='jfg-native-program-bundle', identity=identity(code),
            provenance={k: '3' * 64 for k in ('source_inputs_sha256', 'generator_sha256', 'dependencies_sha256', 'build_receipt_sha256')},
            files=[dict(name=name, size=(runtime / name).stat().st_size, sha256=package.digest(runtime / name)) for name in package.GAME_FILES])
        (runtime / program_bundle.MANIFEST_NAME).write_text(json.dumps(value), encoding='utf-8')

    def update_program(self, files, change, revision='jfg-us-r0'):
        name = 'runtimes/' + revision + '/' + program_bundle.MANIFEST_NAME
        program = json.loads(files[name]); change(program)
        files[name] = json.dumps(program).encode()
        index = json.loads(files['jfg-package.json'])
        for entry in index['runtimes']:
            if entry['revision_id'] == revision:
                entry['manifest_sha256'] = hashlib.sha256(files[name]).hexdigest()
        files['jfg-package.json'] = json.dumps(index).encode()

    def test_complete_playable_bundle(self):
        self.assertEqual(len(release.verify_bundle(self.root, self.metadata)), 3)

    def test_wrong_source_and_version_rejected(self):
        with self.assertRaisesRegex(ValueError, 'source or version'):
            release.verify_bundle(self.root, {**self.metadata, 'commit': '0' * 40})

    def test_bad_checksum_rejected(self):
        self.archive.with_suffix('.sha256').write_text('0' * 64 + '  ' + self.archive.name)
        with self.assertRaisesRegex(ValueError, 'checksum'):
            release.verify_bundle(self.root, self.metadata)

    def rewrite(self, change):
        with zipfile.ZipFile(self.archive) as z: files = {name: z.read(name) for name in z.namelist()}
        change(files)
        with zipfile.ZipFile(self.archive, 'w') as z:
            for name, data in files.items(): z.writestr(name, data)
        self.inventory['members'] = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
        self.inventory['sha256'] = package.digest(self.archive)
        self.inventory_path.write_text(json.dumps(self.inventory))
        self.archive.with_suffix('.sha256').write_text(self.inventory['sha256'] + '  ' + self.archive.name + '\n')

    def test_launcher_only_package_rejected(self):
        self.rewrite(lambda files: files.pop('runtimes/jfg-us-r0/jfg-native-boot.exe'))
        with self.assertRaisesRegex(ValueError, 'playable runtime'):
            release.verify_bundle(self.root, self.metadata)

    def test_game_asset_or_rom_rejected_even_with_updated_inventory(self):
        self.rewrite(lambda files: files.update({'game.z64': b'PRIVATE-CANARY'}))
        with self.assertRaisesRegex(ValueError, 'Unexpected bundle member'):
            release.verify_bundle(self.root, self.metadata)

    def test_runtime_manifest_tampering_rejected(self):
        def change(files):
            self.update_program(files, lambda manifest: manifest['files'][0].update(size=manifest['files'][0]['size'] + 1))
        self.rewrite(change)
        with self.assertRaisesRegex(ValueError, 'digest mismatch'):
            release.verify_bundle(self.root, self.metadata)

    def test_stable_package_requires_clean_launcher_identity(self):
        receipt = self.launcher.parent / 'launcher-build.json'
        receipt.write_text(json.dumps({'source_commit': 'fixture', 'executable_sha256': package.digest(self.launcher), 'inputs': {}}))
        def git(args, **kwargs): return 'fixture' if args[1] == 'rev-parse' else ''
        with mock.patch.object(package.subprocess, 'check_output', side_effect=git):
            archive = package.package(self.launcher, self.runtime, self.root / 'stable', '1.1.0')
        self.assertTrue(archive.is_file())
        dirty_parent = self.root / 'dirty-case'; dirty_parent.mkdir()
        with mock.patch.object(package.subprocess, 'check_output', side_effect=['fixture', ' M changed.cs']):
            with self.assertRaisesRegex(ValueError, 'clean source'):
                package.package(self.launcher, self.runtime, dirty_parent / 'bundle', '1.1.0')

    def test_three_revision_producer_verifier_roundtrip(self):
        runtimes = [self.runtime]
        for code in ('pal', 'jpn'):
            runtime = self.root / code; runtime.mkdir()
            for name in package.RUNTIME_FILES:
                (runtime / name).write_bytes(b'MZsynthetic-runtime')
            (runtime / 'jfg-native-boot.exe.support').write_bytes((self.runtime / 'jfg-native-boot.exe.support').read_bytes())
            self.write_manifest(runtime, code); runtimes.append(runtime)
        output = self.root / 'multi'; output.mkdir()
        archive = package.package(self.launcher, runtimes, output / 'bundle', self.version)
        self.assertEqual(release.verify_bundle(output, self.metadata)[0], archive)

    def test_each_single_revision_roundtrip(self):
        for code in ('pal', 'jpn'):
            with self.subTest(code=code):
                self.write_manifest(self.runtime, code)
                output = self.root / code; output.mkdir()
                package.package(self.launcher, self.runtime, output / 'bundle', self.version)
                self.assertEqual(len(release.verify_bundle(output, self.metadata)), 3)

    def test_duplicate_revision_rejected(self):
        def change(files):
            value = json.loads(files['jfg-package.json'])
            value['runtimes'].append(dict(value['runtimes'][0]))
            files['jfg-package.json'] = json.dumps(value).encode()
        self.rewrite(change)
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            release.verify_bundle(self.root, self.metadata)

    def test_cross_revision_program_rejected_after_rehash(self):
        self.rewrite(lambda files: self.update_program(files, lambda value: value.update(identity=identity('pal'))))
        with self.assertRaisesRegex(ValueError, 'Regional program identity'):
            release.verify_bundle(self.root, self.metadata)

    def test_stale_program_index_hash_rejected(self):
        def change(files):
            key = 'runtimes/jfg-us-r0/jfg-program.json'; files[key] += b' '
        self.rewrite(change)
        with self.assertRaisesRegex(ValueError, 'manifest digest'):
            release.verify_bundle(self.root, self.metadata)

    def test_missing_crt_rejected_even_if_program_and_inventory_rehashed(self):
        self.rewrite(lambda files: self.update_program(files, lambda value: value['files'].pop()))
        with self.assertRaisesRegex(ValueError, 'required libraries'):
            release.verify_bundle(self.root, self.metadata)

    def test_undeclared_regional_runtime_rejected(self):
        self.rewrite(lambda files: files.update({'runtimes/jfg-pal-r0/jfg-native-boot.exe': b'MZextra'}))
        with self.assertRaisesRegex(ValueError, 'Unexpected bundle member'):
            release.verify_bundle(self.root, self.metadata)

    def test_dirty_or_mismatched_support_receipt_rejected(self):
        key = 'runtimes/jfg-us-r0/jfg-native-boot.exe.support'
        self.rewrite(lambda files: files.update({key: files[key].replace(b'build_dirty=0', b'build_dirty=1')}))
        with self.assertRaisesRegex(ValueError, 'Runtime build identity'):
            release.verify_bundle(self.root, self.metadata)

    def test_cross_revision_source_inventory_rejected(self):
        self.inventory['runtime_sources'] = {'jfg-pal-r0': 'fixture'}
        self.inventory_path.write_text(json.dumps(self.inventory))
        with self.assertRaisesRegex(ValueError, 'source inventory'):
            release.verify_bundle(self.root, self.metadata)

    def test_unsafe_license_path_rejected(self):
        self.rewrite(lambda files: files.update({'licenses/../private.txt': b'canary'}))
        with self.assertRaisesRegex(ValueError, 'Unsafe bundle path'):
            release.verify_bundle(self.root, self.metadata)


class DraftPublicationTests(unittest.TestCase):
    def publish(self, draft=True, assets=None, tag='v1.1.0'):
        metadata = {'tag': 'v1.1.0', 'version': '1.1.0', 'commit': 'fixture', 'prerelease': False}
        paths = [Path('bundle.zip'), Path('bundle.sha256'), Path('bundle.inventory.json')]
        response = {'isDraft': draft, 'tagName': tag, 'url': 'https://example.invalid/release',
                    'assets': assets if assets is not None else [{'name': p.name} for p in paths]}
        with mock.patch('sys.argv', ['release_prebuilt.py', 'publish', '--output', '.']), \
             mock.patch.dict(release.os.environ, {'GITHUB_REPOSITORY': 'owner/repo'}), \
             mock.patch.object(release, 'release_metadata', return_value=metadata), \
             mock.patch.object(release, 'verify_bundle', return_value=paths), \
             mock.patch.object(release.subprocess, 'check_output', return_value=json.dumps(response)) as lookup, \
             mock.patch.object(release.subprocess, 'run') as edit:
            try:
                result = release.main()
            except ValueError:
                edit.assert_not_called()
                raise
            self.assertEqual(result, 0)
            self.assertEqual(lookup.call_args.args[0][:4], ['gh', 'release', 'view', 'v1.1.0'])
            self.assertIn('--draft=false', edit.call_args.args[0])

    def test_authenticated_draft_lookup_publishes_verified_bundle(self):
        self.publish()

    def test_public_release_cannot_be_overwritten(self):
        with self.assertRaisesRegex(ValueError, 'already public'):
            self.publish(draft=False)

    def test_different_assets_or_tag_cannot_be_published(self):
        with self.assertRaisesRegex(ValueError, 'assets differ'):
            self.publish(assets=[])
        with self.assertRaisesRegex(ValueError, 'tag differs'):
            self.publish(tag='v9.0.0')

if __name__ == '__main__': unittest.main()
