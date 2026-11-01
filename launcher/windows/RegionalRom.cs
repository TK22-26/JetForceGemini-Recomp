using System;
using System.IO;
using System.Text;

namespace JfgLauncher
{
    // The catalog owns identity. Extensions and country bytes never select a revision.
    internal static class RegionalRom
    {
        internal sealed class Image
        {
            internal readonly RomCatalogEntry Revision;
            internal readonly byte[] CanonicalBytes;
            internal readonly string SourceByteOrder;
            internal Image(RomCatalogEntry revision, byte[] bytes, string order)
            { Revision = revision; CanonicalBytes = bytes; SourceByteOrder = order; }
        }

        internal static RomCatalogEntry Revision(string id)
        {
            foreach (var entry in RomCatalog.Revisions) if (entry.Id == id) return entry;
            throw new InvalidDataException("Unknown ROM revision: " + id);
        }

        internal static Image Read(Stream input) { return Read(input, RomCatalog.Revisions); }

        // A supplied catalog lets ROM-free tests exercise the production normalization path.
        internal static Image Read(Stream input, RomCatalogEntry[] catalog)
        {
            bool sizeKnown = false;
            if (input.CanSeek)
                foreach (var entry in catalog) if (entry.Size == input.Length) sizeKnown = true;
            if (!sizeKnown || input.Length < 64 || input.Length > 33554432 || input.Length % 4 != 0)
                throw new InvalidDataException("Unsupported ROM size. Select an original 32 MiB US, PAL or Japanese retail ROM.");
            byte[] bytes = new byte[(int)input.Length];
            input.Position = 0;
            for (int offset = 0; offset < bytes.Length;)
            {
                int count = input.Read(bytes, offset, bytes.Length - offset);
                if (count == 0) throw new InvalidDataException("The ROM ended before its declared size.");
                offset += count;
            }
            uint magic = ((uint)bytes[0] << 24) | ((uint)bytes[1] << 16) | ((uint)bytes[2] << 8) | bytes[3];
            string order;
            if (magic == 0x80371240) order = "big-endian";
            else if (magic == 0x37804012)
            {
                order = "byte-swapped";
                for (int i = 0; i < bytes.Length; i += 2) { byte b = bytes[i]; bytes[i] = bytes[i+1]; bytes[i+1] = b; }
            }
            else if (magic == 0x40123780)
            {
                order = "little-endian";
                for (int i = 0; i < bytes.Length; i += 4) Array.Reverse(bytes, i, 4);
            }
            else throw new InvalidDataException("The ROM has an unsupported N64 byte order.");
            string digest;
            using (var canonical = new MemoryStream(bytes, false)) digest = LocalSetup.Digest(canonical);
            foreach (var entry in catalog)
                if (entry.Size == bytes.Length && entry.Sha1 == digest)
                {
                    if (bytes[0x3e] != entry.Country || bytes[0x3f] != entry.Revision)
                        throw new InvalidDataException("The ROM header disagrees with its catalog identity.");
                    input.Position = 0;
                    return new Image(entry, bytes, order);
                }
            throw new InvalidDataException("This ROM does not match a supported original US, PAL or Japanese retail revision.");
        }

        internal static RomCatalogEntry Identify(string path)
        {
            using (var input = new FileStream(LocalSetup.FullPath(path), FileMode.Open, FileAccess.Read, FileShare.Read))
                return Read(input).Revision;
        }
    }

    // PowerShell setup loads this assembly before any prerequisite installation.
    // ROM identity and admission remain owned by the same generated catalog.
    public static class SetupRomValidation
    {
        internal static string RequireAdmission(RomCatalogEntry revision)
        {
            if (!revision.NativeBuildAdmitted)
                throw new InvalidDataException(revision.Title + " is recognized, but native Play is not yet qualified.");
            return revision.Id;
        }
        public static string Validate(string path)
        { return RequireAdmission(RegionalRom.Identify(path)); }
    }

    internal static class RegionalStorage
    {
        internal const string MarkerName = "rom-revision.txt";
        internal static string Profile(string sharedProfile, RomCatalogEntry revision, bool navigation)
        {
            revision = RegionalRom.Revision(revision.Id);
            string root = LocalSetup.FullPath(sharedProfile);
            // The pre-regional product used this exact directory for US saves.
            if (revision.Code == "us") return navigation ? LocalSetup.NavigationProfile(root) : root;
            string target = Path.Combine(root, "revisions", revision.Id);
            return navigation ? Path.Combine(target, "navigation-mod") : target;
        }

        internal static void OrdinaryDirectory(string path)
        {
            Directory.CreateDirectory(path);
            if ((File.GetAttributes(path) & FileAttributes.ReparsePoint) != 0)
                throw new InvalidDataException("Revision storage must be an ordinary local folder.");
        }

        internal static string Prepare(string sharedProfile, RomCatalogEntry revision, bool navigation)
        {
            revision = RegionalRom.Revision(revision.Id);
            string root = LocalSetup.FullPath(sharedProfile);
            OrdinaryDirectory(root);
            if (revision.Code != "us")
            {
                OrdinaryDirectory(Path.Combine(root, "revisions"));
                OrdinaryDirectory(Path.Combine(root, "revisions", revision.Id));
            }
            string target = Profile(root, revision, navigation);
            OrdinaryDirectory(target);
            string marker = Path.Combine(target, MarkerName);
            string identity = "jfg-save-namespace-1\n" + revision.Id + "\n" + revision.Sha1 + "\n";
            if (!File.Exists(marker))
            {
                // Only the historical US namespace has an established migration identity.
                if (revision.Code != "us" && (File.Exists(Path.Combine(target, "jfg.flash")) ||
                    File.Exists(Path.Combine(target, "controller-1.pak"))))
                    throw new InvalidDataException("This save folder has no revision identity. Preserve its files and select an empty regional profile.");
                string temporary = marker + "." + Guid.NewGuid().ToString("N") + ".tmp";
                try
                {
                    using (var output = new FileStream(temporary, FileMode.CreateNew, FileAccess.Write, FileShare.None))
                    {
                        byte[] bytes = Encoding.ASCII.GetBytes(identity);
                        output.Write(bytes, 0, bytes.Length); output.Flush(true);
                    }
                    try { File.Move(temporary, marker); }
                    catch (IOException) { if (!File.Exists(marker)) throw; }
                }
                finally { if (File.Exists(temporary)) File.Delete(temporary); }
            }
            if ((File.GetAttributes(marker) & FileAttributes.ReparsePoint) != 0 || new FileInfo(marker).Length > 256 ||
                Encoding.ASCII.GetString(File.ReadAllBytes(marker)) != identity)
                throw new InvalidDataException("The save folder belongs to another ROM revision or has an invalid identity.");
            return target;
        }
    }
}
