"""Metadata edits cannot change loaded bytes or guess symbol ownership."""
import struct,unittest
from types import SimpleNamespace
from scripts.regional.elf_metadata import edit_symbols,prove_loaded_bytes

def fixture():
    data=bytearray(212);data[:7]=b'\x7fELF\x01\x02\x01';struct.pack_into('>I',data,32,52);struct.pack_into('>HH',data,46,40,3)
    struct.pack_into('>10I',data,92,0,3,0,0,172,6,0,0,1,0)
    struct.pack_into('>10I',data,132,0,2,0,0,180,32,1,0,4,16)
    data[172:178]=b'\0leaf\0';struct.pack_into('>IIIBBH',data,196,1,0x80001000,12,0x12,0,5)
    return bytes(data)

class MetadataEdits(unittest.TestCase):
    def test_edit_requires_exact_prior_fields_and_only_changes_symbol_metadata(self):
        original=fixture();changed=edit_symbols(original,{'leaf':([0x80001000,12,2,5],[0x80001000,12,1,5])})
        self.assertEqual([i for i,(a,b) in enumerate(zip(original,changed)) if a!=b],[208])
        self.assertEqual(changed[208],0x11)
    def test_stale_symbol_is_rejected(self):
        with self.assertRaises(ValueError):edit_symbols(fixture(),{'leaf':([0x80001000,16,2,5],[0x80001000,12,1,5])})
    def test_missing_symbol_is_rejected(self):
        with self.assertRaises(ValueError):edit_symbols(fixture(),{'absent':([0,0,2,5],[0,4,2,5])})
    def test_truncated_headers_and_symbol_table_are_rejected(self):
        for data in (b'',fixture()[:120],fixture()[:-1]):
            with self.subTest(length=len(data)),self.assertRaises(ValueError):edit_symbols(data,{})
    def test_bad_symbol_string_is_rejected(self):
        data=bytearray(fixture());struct.pack_into('>I',data,196,99)
        with self.assertRaises(ValueError):edit_symbols(data,{})
    def test_symbol_replacement_cannot_overflow(self):
        with self.assertRaises(ValueError):edit_symbols(fixture(),{'leaf':([0x80001000,12,2,5],[0x100000000,12,1,5])})
    def test_loaded_bytes_can_move_file_offset_but_not_change(self):
        def section(offset,address=0x80000400):return SimpleNamespace(name='.main',section_type='PROGBITS',address=address,size=4,flags='AX',allocated=True,offset=offset)
        prove_loaded_bytes(b'abcd',[section(0)],b'xxabcd',[section(2)])
        with self.assertRaises(ValueError):prove_loaded_bytes(b'abcd',[section(0)],b'xxabce',[section(2)])
        with self.assertRaises(ValueError):prove_loaded_bytes(b'abcd',[section(0)],b'xxabcd',[section(2,0x80000404)])
    def test_truncated_loaded_image_is_rejected(self):
        row=SimpleNamespace(name='.main',section_type='PROGBITS',address=0x80000400,size=4,flags='AX',allocated=True,offset=0)
        with self.assertRaises(ValueError):prove_loaded_bytes(b'abc',[row],b'abcd',[row])

if __name__=='__main__':unittest.main()


class SharedBodyQualification(unittest.TestCase):
    def sample(self):
        from scripts.regional.elf_metadata import sha
        data=bytes(range(24));symbols=[SimpleNamespace(name='body',value=0x1000,size=16),SimpleNamespace(name='entry',value=0x1010,size=8)]
        group={'body_symbol':'body','span_size':24,'span_sha256':sha(data),'members':[{'symbol':s.name,'offset':s.value-0x1000,'size':s.size,'sha256':sha(data[s.value-0x1000:s.value-0x1000+s.size])} for s in symbols]}
        return data,symbols,group
    def test_body_extent_and_alias_preserve_original_coordinates(self):
        from scripts.regional.elf_metadata import qualify_body_alias_groups
        data,symbols,group=self.sample();edits,records=qualify_body_alias_groups([group],symbols,lambda a,n:data[a-0x1000:a-0x1000+n],5)
        self.assertEqual(edits,{'body':([0x1000,16,2,5],[0x1000,24,2,5]),'entry':([0x1010,8,2,5],[0x1010,0,2,5])});self.assertEqual(records[0]['aliases'],['entry'])
    def test_changed_bytes_or_source_extent_rejected(self):
        from scripts.regional.elf_metadata import qualify_body_alias_groups
        data,symbols,group=self.sample()
        with self.assertRaisesRegex(ValueError,'differs'):qualify_body_alias_groups([group],symbols,lambda a,n:b'x'*n,5)
        symbols[1].size=4
        with self.assertRaisesRegex(ValueError,'absent'):qualify_body_alias_groups([group],symbols,lambda a,n:data[a-0x1000:a-0x1000+n],5)
    def test_unclassified_overlap_and_duplicate_groups_rejected(self):
        from scripts.regional.elf_metadata import qualify_body_alias_groups
        data,symbols,group=self.sample();payload=lambda a,n:data[a-0x1000:a-0x1000+n]
        with self.assertRaisesRegex(ValueError,'overlap'):qualify_body_alias_groups([group],symbols+[SimpleNamespace(name='other',value=0x1004,size=4)],payload,5)
        with self.assertRaisesRegex(ValueError,'overlap'):qualify_body_alias_groups([group,group],symbols,payload,5)

    def test_shared_body_proof_rejects_gap_reordered_owner_and_wrong_span_hash(self):
        import copy
        from scripts.regional.elf_metadata import qualify_body_alias_groups
        data,symbols,group=self.sample();payload=lambda a,n:data[a-0x1000:a-0x1000+n]
        variants=[]
        bad=copy.deepcopy(group);bad['members'][1]['offset']=20;variants.append(bad)
        bad=copy.deepcopy(group);bad['body_symbol']='entry';variants.append(bad)
        bad=copy.deepcopy(group);bad['span_sha256']='0'*64;variants.append(bad)
        for bad in variants:
            with self.subTest(group=bad),self.assertRaises(ValueError):qualify_body_alias_groups([bad],symbols,payload,5)
