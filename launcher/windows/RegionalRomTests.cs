using System;
using System.IO;

namespace JfgLauncher
{
    internal static class RegionalRomTests
    {
        private static int checks;
        private static void Check(bool condition, string message) { if (!condition) throw new Exception(message); checks++; }
        private static void Reject(Action action, string message)
        { try { action(); } catch (InvalidDataException) { checks++; return; } throw new Exception(message); }
        internal static int Run(string directory)
        {
            byte[] original = new byte[128]; original[0]=0x80; original[1]=0x37; original[2]=0x12; original[3]=0x40;
            original[0x3e]=(byte)'P'; original[77]=23;
            string digest; using (var input = new MemoryStream(original)) digest=LocalSetup.Digest(input);
            var fixture=new RomCatalogEntry("fixture-pal", "pal", "Fixture", digest, original.Length, (byte)'P', 0, false);
            foreach (int unit in new [] {1,2,4})
            {
                byte[] source=(byte[])original.Clone();
                if (unit>1) for (int i=0; i<source.Length; i+=unit) Array.Reverse(source,i,unit);
                using (var input=new MemoryStream(source, false))
                {
                    var image=RegionalRom.Read(input, new [] {fixture});
                    Check(image.Revision==fixture && image.CanonicalBytes[77]==23, "byte order changed canonical identity");
                    Check(input.Position==0 && source[0] == (unit==1?0x80:unit==2?0x37:0x40), "normalization modified the original");
                }
            }
            var damaged=(byte[])original.Clone();damaged[78]=1;
            Reject(delegate { RegionalRom.Read(new MemoryStream(damaged),new [] {fixture}); },"modified ROM accepted from country header");
            Reject(delegate { RegionalRom.Read(new MemoryStream(original)); },"production catalog accepted synthetic ROM");
            var wrongHeader=new RomCatalogEntry("fixture", "us", "Fixture", digest, original.Length, (byte)'E',0,true);
            Reject(delegate {RegionalRom.Read(new MemoryStream(original),new []{wrongHeader});},"catalog/header disagreement accepted");
            string root=Path.Combine(directory,"regional-storage"); Directory.CreateDirectory(root);
            byte[] oldSave={8,4,2,1};File.WriteAllBytes(Path.Combine(root,"jfg.flash"),oldSave);
            var us=RegionalRom.Revision("jfg-us-r0");var pal=RegionalRom.Revision("jfg-pal-r0");var jp=RegionalRom.Revision("star-twins-jp-r0");
            Check(SetupRomValidation.RequireAdmission(us)==us.Id,"US setup admission lost");
            Reject(delegate { SetupRomValidation.RequireAdmission(pal); },"unqualified PAL setup admitted");
            Reject(delegate { SetupRomValidation.RequireAdmission(jp); },"unqualified JP setup admitted");
            Check(RegionalStorage.Prepare(root,us,false)==root,"legacy US saves moved");
            Check(File.ReadAllBytes(Path.Combine(root,"jfg.flash"))[0]==8,"legacy US save modified");
            string usMarker=Path.Combine(root,RegionalStorage.MarkerName);
            byte[] exactMarker=File.ReadAllBytes(usMarker);
            byte[] bomMarker=new byte[exactMarker.Length+3];bomMarker[0]=0xef;bomMarker[1]=0xbb;bomMarker[2]=0xbf;
            Array.Copy(exactMarker,0,bomMarker,3,exactMarker.Length);File.WriteAllBytes(usMarker,bomMarker);
            Reject(delegate {RegionalStorage.Prepare(root,us,false);},"marker encoding detection changed its byte identity");
            File.WriteAllText(usMarker,System.Text.Encoding.ASCII.GetString(exactMarker).Replace("\n","\r\n"));
            Reject(delegate {RegionalStorage.Prepare(root,us,false);},"marker newline normalization changed its byte identity");
            File.WriteAllBytes(usMarker,exactMarker);

            string palPath=RegionalStorage.Prepare(root,pal,false),jpPath=RegionalStorage.Prepare(root,jp,false);
            Check(palPath!=jpPath && palPath!=root && jpPath!=root,"regional save namespace collision");
            Check(!File.Exists(Path.Combine(palPath,"jfg.flash")) && !File.Exists(Path.Combine(jpPath,"jfg.flash")),"US save copied into another revision");
            Check(RegionalStorage.Prepare(root,pal,false)==palPath,"repeat profile preparation changed identity");
            Check(RegionalStorage.Prepare(root,pal,true)!=RegionalStorage.Prepare(root,jp,true),"navigation profiles overlap");
            File.WriteAllText(Path.Combine(palPath,RegionalStorage.MarkerName),File.ReadAllText(Path.Combine(jpPath,RegionalStorage.MarkerName)));
            Reject(delegate {RegionalStorage.Prepare(root,pal,false);},"mixed-region save identity accepted");
            string unknown=Path.Combine(directory,"unknown-regional-storage");string unknownPath=RegionalStorage.Profile(unknown,pal,false);
            Directory.CreateDirectory(unknownPath);File.WriteAllBytes(Path.Combine(unknownPath,"jfg.flash"),oldSave);
            Reject(delegate {RegionalStorage.Prepare(unknown,pal,false);},"unidentified regional save silently relabeled");
            Check(!File.Exists(Path.Combine(unknownPath,RegionalStorage.MarkerName)),"failed profile preparation published identity");
            return checks;
        }
    }
}
