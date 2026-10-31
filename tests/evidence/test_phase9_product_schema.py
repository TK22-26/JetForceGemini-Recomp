import json
import unittest
from scripts.prepare_generated_sources import _canonical_product, PreparationFailure


class ProductSchemaTests(unittest.TestCase):
    def check(self, kind, version):
        payload = json.dumps({'kind': kind, 'schema_version': version}, sort_keys=True, separators=(',', ':')).encode()
        _canonical_product(payload, kind)

    def test_explicit_sidecar_version(self):
        for version in (1, 2):
            self.check('n64recomp-indirect-decision-sidecar', version)

    def test_unrelated_products_remain_v1(self):
        with self.assertRaises(PreparationFailure):
            self.check('jfg-other-product', 2)

    def test_unsupported_or_noninteger_version(self):
        for version in (0, 3, True, 1.0, 2.0):
            with self.subTest(version=version), self.assertRaises(PreparationFailure):
                self.check('n64recomp-indirect-decision-sidecar', version)
