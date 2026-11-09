using System;
using System.IO;

namespace JfgLauncher
{
    internal static class ImportedRom
    {
        internal static string FileName(string profile)
        {
            return Path.Combine(LocalSetup.FullPath(profile), "roms", "jfg-us.z64");
        }
        internal static string Import(string profile, string source)
        {
            source=LocalSetup.FullPath(source);
            using(var input=new FileStream(source,FileMode.Open,FileAccess.Read,FileShare.Read))
            {
                var image=RegionalRom.Read(input);
                string destination=FileName(profile,image.Revision);
                string folder=Path.GetDirectoryName(destination);
                RegionalStorage.OrdinaryDirectory(LocalSetup.FullPath(profile));
                RegionalStorage.OrdinaryDirectory(folder);
                if(File.Exists(destination) && (File.GetAttributes(destination)&FileAttributes.ReparsePoint)!=0)
                    throw new InvalidDataException("The local ROM copy must be an ordinary file.");
                if(String.Equals(source,destination,StringComparison.OrdinalIgnoreCase) && image.SourceByteOrder=="big-endian")return destination;
                string temporary=destination+"."+Guid.NewGuid().ToString("N")+".tmp";
                try
                {
                    using(var output=new FileStream(temporary,FileMode.CreateNew,FileAccess.ReadWrite,FileShare.None))
                    {
                        output.Write(image.CanonicalBytes,0,image.CanonicalBytes.Length);output.Flush(true);
                        if(RegionalRom.Read(output).Revision.Id!=image.Revision.Id)throw new InvalidDataException("ROM identity changed during import.");
                    }
                    if(File.Exists(destination))File.Replace(temporary,destination,null);else File.Move(temporary,destination);
                    return destination;
                }
                finally {if(File.Exists(temporary))File.Delete(temporary);}
            }
        }
        internal static string FileName(string profile, RomCatalogEntry revision)
        {
            revision=RegionalRom.Revision(revision.Id);
            return revision.Code=="us" ? FileName(profile) : Path.Combine(LocalSetup.FullPath(profile),"roms",revision.Id+".z64");
        }
        // Historical US import fixture entry point. Synthetic tests
        // exercise the same copy/validation/atomic-publication path below.
        internal static string ImportVerified(string profile, string source, long size, string hash)
        {
            source = LocalSetup.FullPath(source);
            string destination = FileName(profile);
            string folder = Path.GetDirectoryName(destination);
            Directory.CreateDirectory(folder);
            if ((File.GetAttributes(folder) & FileAttributes.ReparsePoint) != 0 ||
                (File.Exists(destination) && (File.GetAttributes(destination) & FileAttributes.ReparsePoint) != 0))
                throw new InvalidDataException("The local ROM storage must be an ordinary folder and file.");
            string temporary = destination + "." + Guid.NewGuid().ToString("N") + ".tmp";
            try
            {
                using (var input = new FileStream(source, FileMode.Open, FileAccess.Read, FileShare.Read))
                {
                    LocalSetup.ValidateRom(input, size, hash);
                    if (String.Equals(source, destination, StringComparison.OrdinalIgnoreCase)) return destination;
                    using (var output = new FileStream(temporary, FileMode.CreateNew, FileAccess.ReadWrite, FileShare.None))
                    {
                        input.CopyTo(output);
                        output.Flush(true);
                        LocalSetup.ValidateRom(output, size, hash);
                    }
                }
                // A failed or interrupted import never replaces the prior valid copy.
                if (File.Exists(destination)) File.Replace(temporary, destination, null);
                else File.Move(temporary, destination);
                return destination;
            }
            finally { if (File.Exists(temporary)) File.Delete(temporary); }
        }
    }
    // Library entries earn verification through their full catalog identity.
    internal static class RomLibrary
    {
        internal sealed class Entry { internal RomCatalogEntry Revision; internal string Path, State; }
        internal static RomCatalogEntry Region(string code)
        {
            foreach(var revision in RomCatalog.Revisions)if(revision.Code==code)return revision;
            throw new InvalidDataException("Unknown game region.");
        }
        internal static Entry[] Scan(string profile, Func<string,RomCatalogEntry> identify)
        {
            var result=new Entry[RomCatalog.Revisions.Length];
            for(int i=0;i<result.Length;i++)
            {
                var revision=RomCatalog.Revisions[i];string path=ImportedRom.FileName(profile,revision);
                var entry=new Entry {Revision=revision,Path=path,State="empty"};result[i]=entry;
                if(!File.Exists(path))continue;
                try
                {
                    if((File.GetAttributes(path)&FileAttributes.ReparsePoint)!=0 ||
                       (File.GetAttributes(System.IO.Path.GetDirectoryName(path))&FileAttributes.ReparsePoint)!=0)
                        throw new InvalidDataException("Linked ROM library entry.");
                    entry.State=identify(path).Id==revision.Id ? "verified" : "invalid";
                }
                catch(InvalidDataException){entry.State="invalid";}
                catch(IOException){entry.State="invalid";}
                catch(UnauthorizedAccessException){entry.State="invalid";}
            }
            return result;
        }
        internal static Entry[] Scan(string profile) {return Scan(profile,RegionalRom.Identify);}
        internal static string Snapshot(string selected, Entry[] entries)
        {
            Region(selected);
            var wire=new System.Text.StringBuilder("jfg-rom-library-1\n"+selected+"\n");
            foreach(var entry in entries)
                wire.Append(entry.Revision.Code).Append('\t').Append(entry.State).Append('\t')
                    .Append(entry.State=="verified" ? entry.Path : "").Append('\n');
            return wire.ToString();
        }
    }

}
