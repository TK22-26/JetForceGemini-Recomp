using System;
using System.IO;
using System.Runtime.Serialization.Json;

namespace JfgLauncher
{
    internal static class ProgramBundleTests
    {
        private static int checks;
        private static void Check(bool condition,string message){if(!condition)throw new Exception(message);checks++;}
        private static void Reject(Action action,string message){try{action();}catch(InvalidDataException){checks++;return;}throw new Exception(message);}
        private static ProgramIdentity Identity(string id)
        {
            var revision=RegionalRom.Revision(id);
            var build=new NativeBuildIdentity {Source=new string('4',64),Generated=new string('4',64),Descriptor=new string('4',64),Bindings=new string('4',64),Generator=new string('4',64),Audio=new string('4',64),Dependencies=new string('4',64),Configuration=new string('4',64)};
            build.Hash=build.Compute(id);
            return new ProgramIdentity {Schema=2,Kind="jfg-native-program-identity",RevisionId=id,RomSha1=revision.Sha1,RomSize=revision.Size,
                DescriptorAbi=1,BindingAbi=3,ModelHash=new string('1',64),InputHash=new string('2',64),TvMode=revision.Code=="pal"?0:1,
                Qualification="candidate",BuildIdentity="synthetic-x64",Build=build};
        }
        private static void Write(string directory,ProgramBundle.Manifest manifest)
        {using(var output=File.Create(Path.Combine(directory,ProgramBundle.ManifestName)))new DataContractJsonSerializer(typeof(ProgramBundle.Manifest)).WriteObject(output,manifest);}
        internal static int Run(string root)
        {
            Check(Identity("jfg-us-r0").Build.Hash=="1b15234620a6e69bd2b5333038a02c3cacd710e210800568e167c7be0a3d4e4d","build identity differs from canonical Python producer vector");
            string directory=Path.Combine(root,"regional-bundle");Directory.CreateDirectory(directory);
            var files=new System.Collections.Generic.List<PortablePackage.Entry>();
            byte[] pe=new byte[128];pe[0]=(byte)'M';pe[1]=(byte)'Z';pe[60]=80;pe[80]=(byte)'P';pe[81]=(byte)'E';pe[84]=0x64;pe[85]=0x86;
            foreach(string name in new [] {"jfg-native-boot.exe","SDL2.dll","dxcompiler.dll","dxil.dll"})
            {
                string path=Path.Combine(directory,name);File.WriteAllBytes(path,pe);
                files.Add(new PortablePackage.Entry {Name=name,Size=pe.Length,Sha256=SupportSession.Hash(path)});
            }
            var manifest=new ProgramBundle.Manifest {Schema=1,Kind="jfg-native-program-bundle",Identity=Identity("jfg-us-r0"),
                Origin=new ProgramBundle.Provenance {Source=new string('3',64),Generator=new string('3',64),Dependencies=new string('3',64),Receipt=new string('3',64)},Files=files.ToArray()};
            Write(directory,manifest);var us=RegionalRom.Revision("jfg-us-r0");var pal=RegionalRom.Revision("jfg-pal-r0");
            string executable=Path.Combine(directory,"jfg-native-boot.exe");
            using(var lease=ProgramBundle.Open(executable,us,delegate(string p){return Identity(us.Id);}))
            {
                Check(lease.Identity.RevisionId==us.Id,"matching program bundle rejected");
                try {using(var write=new FileStream(executable,FileMode.Open,FileAccess.Write,FileShare.Read)){}throw new Exception("runtime was writable during the verified session");}
                catch(IOException){checks++;}
            }
            Reject(delegate {using(var lease=ProgramBundle.Open(executable,pal,delegate(string p){return Identity(us.Id);})){}},"mismatched selected ROM accepted");
            manifest.Identity=Identity(pal.Id);Write(directory,manifest);
            Reject(delegate {using(var lease=ProgramBundle.Open(executable,pal,delegate(string p){return Identity(us.Id);})){}},"sidecar relabeled a US binary as PAL");
            manifest.Identity=Identity(us.Id);Write(directory,manifest);
            Check(ProgramBundle.Resolve(directory,us)==executable,"flat regional bundle resolution failed");
            Reject(delegate {ProgramBundle.Resolve(directory,pal);},"resolver chose another revision");
            File.WriteAllBytes(Path.Combine(directory,"SDL2.dll"),new byte[128]);
            Reject(delegate {using(var lease=ProgramBundle.Open(executable,us,delegate(string p){return Identity(us.Id);})){}},"changed dependency accepted");
            foreach(var revision in RomCatalog.Revisions)Check(Identity(revision.Id).Validate()==revision,"regional identity validation differs from catalog");
            var wrong=Identity(us.Id);wrong.InputHash="bad";Reject(delegate{wrong.Validate();},"bad embedded input digest accepted");

            string package=Path.Combine(root,"regional-package");Directory.CreateDirectory(package);
            var packagedEntries=new System.Collections.Generic.List<PortablePackage.RegionalEntry>();
            foreach(var revision in RomCatalog.Revisions)
            {
                string folder=Path.Combine(package,"runtimes",revision.Id);Directory.CreateDirectory(folder);
                var members=new System.Collections.Generic.List<PortablePackage.Entry>();
                foreach(string name in PortablePackage.RuntimeFiles)
                {
                    string member=Path.Combine(folder,name);File.WriteAllBytes(member,pe);
                    members.Add(new PortablePackage.Entry {Name=name,Size=pe.Length,Sha256=SupportSession.Hash(member)});
                }
                var program=new ProgramBundle.Manifest {Schema=1,Kind="jfg-native-program-bundle",Identity=Identity(revision.Id),Origin=manifest.Origin,Files=members.ToArray()};
                Write(folder,program);
                packagedEntries.Add(new PortablePackage.RegionalEntry {Revision=revision.Id,ManifestHash=SupportSession.Hash(Path.Combine(folder,ProgramBundle.ManifestName))});
            }
            string index=Path.Combine(package,"jfg-package.json");
            var packageIndex=new PortablePackage.Manifest {Schema=2,Version="1.0.1-beta.1",Runtimes=packagedEntries.ToArray()};
            Action writeIndex=delegate {using(var output=File.Create(index))new DataContractJsonSerializer(typeof(PortablePackage.Manifest)).WriteObject(output,packageIndex);};
            writeIndex();
            foreach(var revision in RomCatalog.Revisions)
                Check(PortablePackage.ResolveRevision(package,revision)==Path.Combine(package,"runtimes",revision.Id,"jfg-native-boot.exe"),"package chose another revision");
            string retainedHash=packagedEntries[0].ManifestHash;packagedEntries[0].ManifestHash=new string('0',64);writeIndex();
            Reject(delegate {PortablePackage.ResolveRevision(package,RegionalRom.Revision(packagedEntries[0].Revision));},"changed bundle manifest admitted");
            packagedEntries[0].ManifestHash=retainedHash;
            packageIndex.Runtimes=new [] {packagedEntries[0],packagedEntries[0]};writeIndex();
            Reject(delegate {PortablePackage.ResolveRevision(package,us);},"duplicate package revision admitted");
            packageIndex.Runtimes=new [] {new PortablePackage.RegionalEntry {Revision="../outside",ManifestHash=retainedHash}};writeIndex();
            Reject(delegate {PortablePackage.ResolveRevision(package,us);},"package revision path traversal admitted");
            packageIndex.Runtimes=new [] {packagedEntries[0]};writeIndex();
            var missing=RegionalRom.Revision(packagedEntries[1].Revision);
            Reject(delegate {PortablePackage.ResolveRevision(package,missing);},"missing package revision fell back to another bundle");
            packageIndex.Runtimes=packagedEntries.ToArray();writeIndex();
            return checks;
        }
    }
}
