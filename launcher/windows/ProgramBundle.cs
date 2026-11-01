using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.Serialization;
using System.Runtime.Serialization.Json;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading.Tasks;

namespace JfgLauncher
{
    [DataContract]
    internal sealed class NativeBuildIdentity
    {
        [DataMember(Name="source_sha256",IsRequired=true)] public string Source="";
        [DataMember(Name="generated_sources_sha256",IsRequired=true)] public string Generated="";
        [DataMember(Name="descriptor_sha256",IsRequired=true)] public string Descriptor="";
        [DataMember(Name="bindings_sha256",IsRequired=true)] public string Bindings="";
        [DataMember(Name="generator_sha256",IsRequired=true)] public string Generator="";
        [DataMember(Name="audio_sha256",IsRequired=true)] public string Audio="";
        [DataMember(Name="dependencies_sha256",IsRequired=true)] public string Dependencies="";
        [DataMember(Name="configuration_sha256",IsRequired=true)] public string Configuration="";
        [DataMember(Name="build_sha256",IsRequired=true)] public string Hash="";
        internal string Compute(string revision)
        {
            // Canonical ASCII JSON keys sorted identically to the build producer.
            string value="{\"audio_sha256\":\""+Audio+"\",\"bindings_sha256\":\""+Bindings+
                "\",\"configuration_sha256\":\""+Configuration+"\",\"dependencies_sha256\":\""+Dependencies+
                "\",\"descriptor_sha256\":\""+Descriptor+"\",\"generated_sources_sha256\":\""+Generated+
                "\",\"generator_sha256\":\""+Generator+"\",\"revision_id\":\""+revision+"\",\"source_sha256\":\""+Source+"\"}";
            using(var hash=SHA256.Create())return BitConverter.ToString(hash.ComputeHash(Encoding.ASCII.GetBytes(value))).Replace("-","").ToLowerInvariant();
        }
        internal bool Valid(string revision)
        {
            foreach(var hash in new [] {Source,Generated,Descriptor,Bindings,Generator,Audio,Dependencies,Configuration,Hash})
                if(!ProgramBundle.ValidHash(hash))return false;
            return Hash==Compute(revision);
        }
    }

    [DataContract]
    internal sealed class ProgramIdentity
    {
        [DataMember(Name="schema_version",IsRequired=true)] public int Schema=0;
        [DataMember(Name="kind",IsRequired=true)] public string Kind="";
        [DataMember(Name="revision_id",IsRequired=true)] public string RevisionId="";
        [DataMember(Name="rom_sha1",IsRequired=true)] public string RomSha1="";
        [DataMember(Name="rom_size",IsRequired=true)] public long RomSize=0;
        [DataMember(Name="descriptor_abi",IsRequired=true)] public int DescriptorAbi=0;
        [DataMember(Name="binding_abi",IsRequired=true)] public int BindingAbi=0;
        [DataMember(Name="program_model_sha256",IsRequired=true)] public string ModelHash="";
        [DataMember(Name="generation_input_sha256",IsRequired=true)] public string InputHash="";
        [DataMember(Name="initial_tv_mode",IsRequired=true)] public int TvMode=0;
        [DataMember(Name="qualification",IsRequired=true)] public string Qualification="";
        [DataMember(Name="build_identity",IsRequired=true)] public string BuildIdentity="";
        [DataMember(Name="build",IsRequired=true)] public NativeBuildIdentity Build=null;
        internal RomCatalogEntry Validate()
        {
            var revision=RegionalRom.Revision(RevisionId);
            if(Schema!=2 || Kind!="jfg-native-program-identity" || RomSha1!=revision.Sha1 || RomSize!=revision.Size ||
                DescriptorAbi!=1 || BindingAbi!=3 || TvMode!=(revision.Code=="pal"?0:1) || Qualification!="candidate" ||
                !ProgramBundle.ValidHash(ModelHash) || !ProgramBundle.ValidHash(InputHash) || Build==null || !Build.Valid(RevisionId) ||
                BuildIdentity==null || !Regex.IsMatch(BuildIdentity,"\\A[A-Za-z0-9_.+-]{1,128}\\z"))
                throw new InvalidDataException("The runtime has an incompatible program identity.");
            return revision;
        }
        internal bool SameProgram(ProgramIdentity other)
        {
            Validate();other.Validate();
            return RevisionId==other.RevisionId && ModelHash==other.ModelHash && InputHash==other.InputHash &&
                BuildIdentity==other.BuildIdentity && Build.Hash==other.Build.Hash;
        }
    }

    internal static class ProgramBundle
    {
        internal const string ManifestName="jfg-program.json";
        [DataContract] internal sealed class Provenance
        {
            [DataMember(Name="source_inputs_sha256",IsRequired=true)] public string Source="";
            [DataMember(Name="generator_sha256",IsRequired=true)] public string Generator="";
            [DataMember(Name="dependencies_sha256",IsRequired=true)] public string Dependencies="";
            [DataMember(Name="build_receipt_sha256",IsRequired=true)] public string Receipt="";
        }
        [DataContract] internal sealed class Manifest
        {
            [DataMember(Name="schema_version",IsRequired=true)] public int Schema=0;
            [DataMember(Name="kind",IsRequired=true)] public string Kind="";
            [DataMember(Name="identity",IsRequired=true)] public ProgramIdentity Identity=null;
            [DataMember(Name="provenance",IsRequired=true)] public Provenance Origin=null;
            [DataMember(Name="files",IsRequired=true)] public PortablePackage.Entry[] Files=null;
        }
        internal sealed class Lease : IDisposable
        {
            internal readonly List<FileStream> Files=new List<FileStream>();
            internal string Runtime;
            internal ProgramIdentity Identity;
            public void Dispose() { foreach(var stream in Files) stream.Dispose();Files.Clear(); }
        }
        internal static bool ValidHash(string value) { return value!=null && Regex.IsMatch(value,"\\A[0-9a-f]{64}\\z"); }
        internal static T ReadJson<T>(Stream input)
        {
            try { return (T)new DataContractJsonSerializer(typeof(T)).ReadObject(input); }
            catch(SerializationException error) { throw new InvalidDataException("Invalid regional program manifest.",error); }
        }
        internal static Manifest ReadManifest(string directory)
        {
            string path=Path.Combine(directory,ManifestName);
            if(!File.Exists(path) || new FileInfo(path).Length>65536)
                throw new InvalidDataException("This runtime has no regional program manifest. Install or build the matching regional runtime bundle.");
            Manifest value;
            using(var input=File.OpenRead(path))value=ReadJson<Manifest>(input);
            if(value==null || value.Schema!=1 || value.Kind!="jfg-native-program-bundle" || value.Identity==null || value.Origin==null ||
                !ValidHash(value.Origin.Source) || !ValidHash(value.Origin.Generator) || !ValidHash(value.Origin.Dependencies) || !ValidHash(value.Origin.Receipt) || value.Files==null)
                throw new InvalidDataException("The regional program manifest is incomplete.");
            value.Identity.Validate();
            var allowed=new HashSet<string>(PortablePackage.RuntimeFiles,StringComparer.Ordinal);
            var names=new HashSet<string>(StringComparer.Ordinal);
            foreach(var file in value.Files)
                if(file==null || !allowed.Contains(file.Name??"") || !names.Add(file.Name) || file.Size<=0 || !ValidHash(file.Sha256))
                    throw new InvalidDataException("The regional runtime file inventory is invalid.");
            foreach(string required in new [] {"jfg-native-boot.exe","SDL2.dll","dxcompiler.dll","dxil.dll"})
                if(!names.Contains(required))throw new InvalidDataException("The regional runtime is incomplete: "+required);
            return value;
        }
        internal static ProgramIdentity Describe(string executable)
        {
            using(var process=new Process())
            {
                process.StartInfo=new ProcessStartInfo(executable,"--describe") { UseShellExecute=false, CreateNoWindow=true,
                    WorkingDirectory=Path.GetDirectoryName(executable),RedirectStandardOutput=true,RedirectStandardError=true };
                var remove=new List<string>();
                foreach(string key in process.StartInfo.EnvironmentVariables.Keys) if(key.StartsWith("JFG_",StringComparison.OrdinalIgnoreCase)) remove.Add(key);
                foreach(string key in remove)process.StartInfo.EnvironmentVariables.Remove(key);
                process.Start();var stdout=process.StandardOutput.ReadToEndAsync();var stderr=process.StandardError.ReadToEndAsync();
                if(!process.WaitForExit(10000))
                {
                    try{process.Kill();}catch(InvalidOperationException){}
                    throw new InvalidDataException("The runtime did not answer its program identity query.");
                }
                if(!Task.WaitAll(new Task[]{stdout,stderr},1000) || process.ExitCode!=0 || stdout.Result.Length>16384 || stderr.Result.Length!=0)
                    throw new InvalidDataException("The runtime could not verify its program identity.");
                using(var input=new MemoryStream(Encoding.UTF8.GetBytes(stdout.Result)))
                { var value=ReadJson<ProgramIdentity>(input);if(value==null)throw new InvalidDataException("Empty program identity.");value.Validate();return value; }
            }
        }
        internal static Lease Open(string runtime,RomCatalogEntry revision)
        { return Open(runtime,revision,Describe); }
        internal static Lease Open(string runtime,RomCatalogEntry revision,Func<string,ProgramIdentity> query)
        {
            string full=LocalSetup.ValidateRuntime(runtime);
            var manifest=ReadManifest(Path.GetDirectoryName(full));
            if(manifest.Identity.RevisionId!=revision.Id)throw new InvalidDataException("The selected runtime belongs to a different ROM revision.");
            var lease=new Lease {Runtime=full,Identity=manifest.Identity};
            try
            {
                foreach(var entry in manifest.Files)
                {
                    string path=Path.Combine(Path.GetDirectoryName(full),entry.Name);
                    if(!File.Exists(path) || (File.GetAttributes(path)&FileAttributes.ReparsePoint)!=0)
                        throw new InvalidDataException("Missing or redirected regional runtime member: "+entry.Name);
                    var input=new FileStream(path,FileMode.Open,FileAccess.Read,FileShare.Read);lease.Files.Add(input);
                    string hash;using(var sha=SHA256.Create())hash=BitConverter.ToString(sha.ComputeHash(input)).Replace("-","").ToLowerInvariant();
                    if(input.Length!=entry.Size || hash!=entry.Sha256)throw new InvalidDataException("Regional runtime member has changed: "+entry.Name);
                }
                if(!manifest.Identity.SameProgram(query(full)))throw new InvalidDataException("The manifest does not match the program embedded in this runtime.");
                return lease;
            }
            catch {lease.Dispose();throw;}
        }
        internal static string Resolve(string directory,RomCatalogEntry revision)
        {
            directory=LocalSetup.FullPath(directory);
            foreach(string candidate in new [] {Path.Combine(directory,"runtimes",revision.Id),directory})
            {
                if(!File.Exists(Path.Combine(candidate,ManifestName)))continue;
                var manifest=ReadManifest(candidate);
                if(manifest.Identity.RevisionId==revision.Id)return LocalSetup.ValidateRuntime(Path.Combine(candidate,"jfg-native-boot.exe"));
            }
            throw new InvalidDataException("No matching runtime is installed for "+revision.Title+" ("+revision.Code+").");
        }
    }

    internal sealed class RegionalSession : IDisposable
    {
        internal RomCatalogEntry Revision;
        internal string Profile;
        internal ProcessStartInfo StartInfo;
        private FileStream romLease;
        private ProgramBundle.Lease bundleLease;
        internal static RegionalSession Open(string runtime,string rom,string preferences,bool navigation)
        {
            var session=new RegionalSession();
            try
            {
                session.Revision=RegionalRom.Identify(rom);
                if(!session.Revision.NativeBuildAdmitted)
                    throw new InvalidDataException(session.Revision.Title+" is recognized, but native gameplay support is still being qualified.");
                session.romLease=LocalSetup.OpenVerifiedRom(rom,session.Revision);
                session.bundleLease=ProgramBundle.Open(runtime,session.Revision);
                // Writable profile preparation happens only after the exact ROM and binary agree.
                string campaign=RegionalStorage.Prepare(preferences,session.Revision,false);
                session.Profile=RegionalStorage.Prepare(preferences,session.Revision,navigation);
                if(navigation)
                {
                    string initialized=Path.Combine(session.Profile,"initialized.txt");
                    if(!File.Exists(initialized))
                    {
                        foreach(string name in new [] {"jfg.flash","controller-1.pak"})
                        {
                            string source=Path.Combine(campaign,name),target=Path.Combine(session.Profile,name);
                            if(!File.Exists(source)||File.Exists(target))continue;
                            string temporary=target+"."+Guid.NewGuid().ToString("N")+".tmp";
                            try {File.Copy(source,temporary,false);File.Move(temporary,target);}
                            finally {if(File.Exists(temporary))File.Delete(temporary);}
                        }
                        File.WriteAllText(initialized,"Separate navigation saves for "+session.Revision.Id+".\n");
                    }
                }
                session.StartInfo=LocalSetup.StartInfo(runtime,rom,session.Profile);
                session.StartInfo.EnvironmentVariables["JFG_MASTER_VOLUME_CONFIG"]=AudioPreferences.FileName(preferences);
                session.StartInfo.EnvironmentVariables["JFG_VIDEO_CONFIG"]=Path.Combine(preferences,"video.ini");
                if(File.Exists(ControllerProfile.FileName(preferences)))
                { ControllerProfile.Load(preferences);session.StartInfo.EnvironmentVariables["JFG_CONTROLLER_CONFIG"]=ControllerProfile.FileName(preferences); }
                string exports=Path.Combine(session.Profile,"maps",DateTime.UtcNow.ToString("yyyyMMdd-HHmmss")+"-"+Guid.NewGuid().ToString("N"));
                session.StartInfo.EnvironmentVariables[navigation?"JFG_MOD_OUTPUT":"JFG_LIVE_OUTPUT"]=exports;
                if(navigation)session.StartInfo.EnvironmentVariables["JFG_NAVIGATION_MOD"]="1";
                MapModPreferences.PrepareSession(preferences,exports);
                return session;
            }
            catch {session.Dispose();throw;}
        }
        public void Dispose() {if(romLease!=null)romLease.Dispose();if(bundleLease!=null)bundleLease.Dispose();}
    }
}
