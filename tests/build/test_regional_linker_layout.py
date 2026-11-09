import hashlib,struct,unittest
from scripts.regional.linker_layout import immediate_pair,decode_domains

class LinkerDomainTests(unittest.TestCase):
    def test_signed_low_half_is_decoded_without_address_delta(self):
        self.assertEqual(immediate_pair(struct.pack('>II',0x3c028010,0x2442e500),0,4),0x800fe500)
    def test_register_and_opcode_mismatches_are_rejected(self):
        for high,low in ((0x3c028010,0x2443e500),(0x3c028010,0x3442e500),(0x3c028010,0x2462e500)):
            with self.assertRaises(ValueError):immediate_pair(struct.pack('>II',high,low),0,4)
    def test_original_data_boundary_need_not_equal_extractor_text_end(self):
        body=struct.pack('>8I',0x3c028000,0x24420450,0x3c03800a,0x246308d0,0x3c04800a,0x248408d0,0x3c05800b,0x24a50e30)
        recipe={'resolver_body_sha256':hashlib.sha256(body).hexdigest(),'resolver_body_size':len(body),'code_pairs':[[0,4]],'data_pairs':[[8,12],[16,20]],'bss_pairs':[[24,28]]}
        self.assertEqual(decode_domains(body,recipe),(0x80000450,0x800a08d0,0x800b0e30))
        bad=bytearray(body);bad[23]^=4
        with self.assertRaises(ValueError):decode_domains(bytes(bad),recipe)
        recipe['resolver_body_sha256']=hashlib.sha256(bad).hexdigest()
        with self.assertRaisesRegex(ValueError,'disagree'):decode_domains(bytes(bad),recipe)

if __name__=='__main__':unittest.main()
