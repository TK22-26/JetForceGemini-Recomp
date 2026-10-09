using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Runtime.Serialization;
using System.Runtime.Serialization.Json;
using System.Threading.Tasks;
using System.Windows.Forms;
namespace JfgLauncher {
    [DataContract] internal sealed class CharacterInventory {
        [DataMember] public int id=0,weapons=0;
        [DataMember] public bool[] items=null;
    }
    [DataContract] internal sealed class InventoryTracker {
        [DataMember] public bool known=false;
        [DataMember] public int current=-1;
        [DataMember] public CharacterInventory[] characters=null;
        [DataMember] public bool[] shared=null;
        internal void Validate() {
            if(!known)return;
            if(current<0||current>2||characters==null||characters.Length!=3||shared==null||shared.Length!=12)
                throw new InvalidDataException("Inventory telemetry is incomplete.");
            bool[] seen=new bool[3];
            foreach(var c in characters) {
                if(c==null||c.id<0||c.id>2||seen[c.id]||c.weapons<0||c.weapons>65535||c.items==null||(c.items.Length!=27&&c.items.Length!=28))
                    throw new InvalidDataException("Invalid character inventory.");
                seen[c.id]=true;
            }
        }
    }
    internal static class ToolColors {
        internal static readonly Color Background=Color.FromArgb(11,15,23),Panel=Color.FromArgb(14,19,32),
            Border=Color.FromArgb(46,58,87),Text=Color.FromArgb(232,236,244),Muted=Color.FromArgb(134,145,168),
            Amber=Color.FromArgb(255,178,62),Blue=Color.FromArgb(111,211,238);
        internal static Button Button(string text) {
            var button=new Button{Text=text,FlatStyle=FlatStyle.Flat,BackColor=Panel,ForeColor=Text,UseVisualStyleBackColor=false};
            button.FlatAppearance.BorderColor=Border;button.FlatAppearance.MouseOverBackColor=Color.FromArgb(32,42,62);return button;
        }
    }
    // PID and process creation time prevent old exports or a reused PID from
    // masquerading as a running game. No inventory contents are saved here.
    internal static class InventorySession {
        internal static void Record(string directory,System.Diagnostics.Process process) {
            try {
                Directory.CreateDirectory(directory);
                File.WriteAllText(Path.Combine(directory,"inventory-session.txt"),process.Id.ToString(System.Globalization.CultureInfo.InvariantCulture)+"\n"+process.StartTime.ToUniversalTime().Ticks.ToString(System.Globalization.CultureInfo.InvariantCulture));
            }catch(IOException){}catch(UnauthorizedAccessException){}catch(InvalidOperationException){}catch(System.ComponentModel.Win32Exception){}
        }
        internal static bool IsActive(string directory) {
            try {
                string path=Path.Combine(directory,"inventory-session.txt");
                if(!File.Exists(path)||new FileInfo(path).Length>128)return false;
                string[] fields=File.ReadAllLines(path);int pid;long started;
                if(fields.Length!=2||!Int32.TryParse(fields[0],out pid)||!Int64.TryParse(fields[1],out started))return false;
                using(var process=System.Diagnostics.Process.GetProcessById(pid))
                    return !process.HasExited&&process.StartTime.ToUniversalTime().Ticks==started;
            }catch(IOException){}catch(UnauthorizedAccessException){}catch(ArgumentException){}catch(InvalidOperationException){}catch(System.ComponentModel.Win32Exception){}
            return false;
        }
    }
    internal sealed class InventoryWindow: ApplicationWindow {
        private string directory;
        private readonly Func<bool> gameActive;
        private readonly CheckBox follow=new CheckBox{Text="\u25ce",Font=new Font("Segoe UI",14),Checked=true,Appearance=Appearance.Button,TextAlign=ContentAlignment.MiddleCenter,FlatStyle=FlatStyle.Flat,Width=48,Height=36,AccessibleName="Follow active character"};
        private readonly Label status=new Label{Dock=DockStyle.Fill,TextAlign=ContentAlignment.MiddleRight,ForeColor=ToolColors.Blue,Text="NO GAME RUNNING",Padding=new Padding(0,0,14,0)};
        private readonly Label details=new Label{Dock=DockStyle.Bottom,Height=72,Padding=new Padding(16,12,16,8),BackColor=ToolColors.Panel};
        private readonly Label artStatus=new Label{Dock=DockStyle.Bottom,Height=30,Padding=new Padding(12,5,0,0),ForeColor=ToolColors.Muted,Text="Item images: select a supported ROM in the launcher."};
        private readonly Timer timer=new Timer{Interval=500};
        private readonly InventoryCanvas canvas=new InventoryCanvas{Dock=DockStyle.Fill};
        private readonly Button[] characters=new Button[3];
        private readonly ToolTip characterTips=new ToolTip();
        private InventoryTracker value;
        private int selected=1;
        private Dictionary<int,Bitmap> images;
        internal int SelectedCharacter {get{return selected;}}
        internal InventoryWindow(string path):this(path,LocalSetup.LoadSettings(LocalSetup.ProfileRoot).RomPath){}
        internal InventoryWindow(string path,string romPath):this(path,romPath,null){}
        internal InventoryWindow(string path,string romPath,Func<bool> isGameActive) {
            directory=path;gameActive=isGameActive??delegate{return InventorySession.IsActive(directory);};Text="JFG Live Inventory";ClientSize=new Size(470,790);MinimumSize=new Size(450,580);
            DoubleBuffered=true;AutoScaleMode=AutoScaleMode.Dpi;Font=new Font("Segoe UI",9);BackColor=ToolColors.Background;ForeColor=ToolColors.Text;
            var header=new Panel{Dock=DockStyle.Top,Height=42,BackColor=ToolColors.Panel};
            header.Controls.Add(status);header.Controls.Add(new Label{Text="INVENTORY",Dock=DockStyle.Left,Width=165,Padding=new Padding(16,12,0,0),Font=new Font(Font,FontStyle.Bold)});
            var rail=new FlowLayoutPanel{Dock=DockStyle.Right,Width=68,Padding=new Padding(4,14,0,0),BackColor=ToolColors.Panel,FlowDirection=FlowDirection.TopDown};
            string[] names={"Vela","Juno","Lupus"};
            foreach(int id in new[]{1,0,2}) {
                int character=id;var button=new CharacterButton{Text=names[id].Substring(0,1),FlatStyle=FlatStyle.Flat,BackColor=ToolColors.Panel,ForeColor=ToolColors.Text};button.Size=new Size(56,56);button.AccessibleName=names[id];
                button.Click+=delegate{follow.Checked=false;selected=character;UpdateSelection();};characters[id]=button;characterTips.SetToolTip(button,names[id]);rail.Controls.Add(button);
            }
            follow.Margin=new Padding(0,16,0,0);follow.ForeColor=ToolColors.Blue;follow.BackColor=ToolColors.Panel;follow.FlatAppearance.CheckedBackColor=Color.FromArgb(23,56,66);follow.FlatAppearance.BorderColor=ToolColors.Border;rail.Controls.Add(follow);rail.Controls.Add(new Label{Text="FOLLOW",Width=48,Height=20,TextAlign=ContentAlignment.MiddleCenter,ForeColor=ToolColors.Muted,Font=new Font("Segoe UI",6.5f)});
            Controls.Add(canvas);Controls.Add(rail);Controls.Add(artStatus);Controls.Add(details);Controls.Add(header);
            canvas.SelectionChanged+=delegate{UpdateDetails();};follow.CheckedChanged+=delegate{if(follow.Checked&&value!=null)selected=value.current;UpdateSelection();};
            timer.Tick+=delegate{RefreshInventory();};
            Shown+=async delegate {
                RefreshInventory();timer.Start();BeginInvoke(new Action(delegate{Invalidate(true);Update();}));
                if(String.IsNullOrWhiteSpace(romPath))return;
                artStatus.Text="Reading item images from your ROM...";
                try {
                    var result=await Task.Run(delegate{return InventoryImages.Load(romPath);});
                    if(IsDisposed){foreach(var bitmap in result.Values)bitmap.Dispose();return;}
                    images=result;
                    for(int id=0;id<3;id++){Bitmap emblem;if(images.TryGetValue(300+id,out emblem)){characters[id].Image=emblem;characters[id].ImageAlign=ContentAlignment.MiddleCenter;characters[id].Text="";}}
                    canvas.SetImages(images);artStatus.Text="Images from your ROM. Names shown when unavailable.";Invalidate(true);Update();
                }catch(Exception error) {
                    if(IsDisposed)return;
                    if(!(error is InvalidDataException)&&!(error is IOException)&&!(error is UnauthorizedAccessException)&&!(error is ArgumentException))throw;
                    artStatus.Text="Images unavailable; inventory remains readable.";
                    new ToolTip().SetToolTip(artStatus,error.Message);
                }
            };
            FormClosed+=delegate{timer.Stop();timer.Dispose();characterTips.Dispose();if(images!=null)foreach(var image in images.Values)image.Dispose();};
            UpdateSelection();
        }
        internal void BindDirectory(string path){directory=path;value=null;RefreshInventory();}
        internal void Apply(InventoryTracker next,bool live) {
            if(live&&next!=null)next.Validate();value=live&&next!=null&&next.known?next:null;
            status.Text=value==null?"WAITING FOR LIVE DATA":"LIVE";
            status.ForeColor=live?ToolColors.Blue:ToolColors.Muted;
            if(value!=null&&follow.Checked)selected=value.current;UpdateSelection();
        }
        private void UpdateSelection() {
            foreach(int id in new[]{0,1,2}){characters[id].FlatAppearance.BorderColor=id==selected?ToolColors.Amber:ToolColors.Border;characters[id].ForeColor=id==selected?ToolColors.Amber:ToolColors.Muted;}
            canvas.Value=value==null?null:Array.Find(value.characters,delegate(CharacterInventory c){return c.id==selected;});
            canvas.Shared=value==null?null:value.shared;canvas.RefreshTiles();UpdateDetails();
        }
        private void UpdateDetails(){details.Text=canvas.SelectionDescription;}
        private void RefreshInventory() {
            if(!gameActive()) {Apply(null,false);status.Text="NO GAME RUNNING";return;}
            try {
                using(var file=new FileStream(Path.Combine(directory,"live.json"),FileMode.Open,FileAccess.Read,FileShare.ReadWrite|FileShare.Delete)) {
                    if(file.Length>16*1024*1024)throw new InvalidDataException("Inventory export is too large.");
                    var live=(MapLive)new DataContractJsonSerializer(typeof(MapLive)).ReadObject(file);
                    if(live==null||live.schema!=1)throw new InvalidDataException("Unsupported inventory export.");
                    long age=NavigationExplorer.Clock-live.timestamp_ms;Apply(live.inventory_tracker,age>=0&&age<5000);
                }
            }catch(Exception error) {
                if(!(error is InvalidDataException)&&!(error is IOException)&&!(error is UnauthorizedAccessException)&&!(error is SerializationException))throw;
                Apply(null,false);
            }
        }
    }
    internal sealed class CharacterButton:Button {
        internal CharacterButton(){SetStyle(ControlStyles.OptimizedDoubleBuffer|ControlStyles.AllPaintingInWmPaint|ControlStyles.UserPaint,true);UseVisualStyleBackColor=false;}
        protected override void OnPaint(PaintEventArgs e) {
            if(Image==null){base.OnPaint(e);return;}
            e.Graphics.Clear(BackColor);
            using(var pen=new Pen(FlatAppearance.BorderColor,2))e.Graphics.DrawRectangle(pen,1,1,Width-3,Height-3);
            float scale=Math.Min((Width-10f)/Image.Width,(Height-10f)/Image.Height);
            int width=(int)(Image.Width*scale),height=(int)(Image.Height*scale);
            e.Graphics.InterpolationMode=System.Drawing.Drawing2D.InterpolationMode.HighQualityBicubic;
            e.Graphics.DrawImage(Image,new Rectangle((Width-width)/2,(Height-height)/2,width,height));
            if(Focused)ControlPaint.DrawFocusRectangle(e.Graphics,new Rectangle(3,3,Width-6,Height-6),ToolColors.Text,BackColor);
        }
    }
    internal sealed class InventoryTile:Button {
        internal Bitmap Artwork;internal bool Owned,Known,Selected;
        internal string ItemName;internal Color Accent;
        internal InventoryTile(){SetStyle(ControlStyles.OptimizedDoubleBuffer|ControlStyles.AllPaintingInWmPaint|ControlStyles.UserPaint,true);BackColor=ToolColors.Background;ForeColor=ToolColors.Muted;FlatStyle=FlatStyle.Flat;UseVisualStyleBackColor=false;Size=new Size(54,54);Margin=new Padding(3);Font=new Font("Segoe UI",7.5f);}
        protected override void OnPaint(PaintEventArgs e) {
            e.Graphics.Clear(Known&&Owned?Color.FromArgb(29,43,61):ToolColors.Background);
            using(var border=new Pen(Selected?ToolColors.Amber:Known&&Owned?Accent:ToolColors.Border,Selected?2:1))
                e.Graphics.DrawRectangle(border,1,1,Width-3,Height-3);
            if(Focused)ControlPaint.DrawFocusRectangle(e.Graphics,new Rectangle(4,4,Width-8,Height-8),ToolColors.Text,BackColor);
            if(Artwork==null)TextRenderer.DrawText(e.Graphics,ItemName,Font,new Rectangle(3,3,Width-6,Height-6),Known&&Owned?ToolColors.Text:ToolColors.Muted,TextFormatFlags.NoPadding|TextFormatFlags.WordBreak|TextFormatFlags.HorizontalCenter|TextFormatFlags.VerticalCenter|TextFormatFlags.EndEllipsis);
            if(Artwork!=null) {
                float scale=Math.Min((Width-14f)/Artwork.Width,(Height-14f)/Artwork.Height);
                int w=(int)(Artwork.Width*scale),h=(int)(Artwork.Height*scale);
                using(var attributes=new ImageAttributes()) {
                    var matrix=new ColorMatrix();matrix.Matrix33=Known&&Owned?1f:.22f;attributes.SetColorMatrix(matrix);
                    e.Graphics.InterpolationMode=Artwork.Width>64?System.Drawing.Drawing2D.InterpolationMode.HighQualityBicubic:System.Drawing.Drawing2D.InterpolationMode.NearestNeighbor;
                    e.Graphics.PixelOffsetMode=System.Drawing.Drawing2D.PixelOffsetMode.Half;
                    e.Graphics.DrawImage(Artwork,new Rectangle((Width-w)/2,(Height-h)/2,w,h),0,0,Artwork.Width,Artwork.Height,GraphicsUnit.Pixel,attributes);
                }
            }
            if(Known&&Owned)using(var brush=new SolidBrush(Accent))e.Graphics.FillRectangle(brush,Width-8,Height-8,3,3);
        }
    }
    internal sealed class InventoryCanvas:FlowLayoutPanel {
        internal CharacterInventory Value;internal bool[] Shared;
        internal static readonly string[] weapons={"Pistol","Homing missiles","Machine gun","Plasma shotgun","Shocker","Tri-rocket launcher","Flamethrower","Sniper rifle","Grenades","Shurikens","Fish Food","Timed mines","Remote mines","Flares","Cluster bombs"};
        private static readonly string[] parts={"Power cell","Radar dish","Fin","Cargo bay key","Deflector shield","Fuse","Vela's hatch key","Juno's hatch key","Lupus's hatch key","Nitrogen tank","Oxygen tank","Stabilizer"};
        private static readonly int[] itemIds={0,1,2,3,9,16,17,20,21,22,23,24,25,26,27};
        private readonly List<InventoryTile[]> tiles=new List<InventoryTile[]>();
        private readonly List<Label> headings=new List<Label>();private readonly ToolTip tips=new ToolTip();
        private readonly string[] categories={"WEAPONS","KEYS & QUEST","SHIP PARTS  /  SHARED"};
        private int selectedGroup,selectedItem;
        internal event Action SelectionChanged;
        internal string SelectionDescription {get {var tile=tiles[selectedGroup][selectedItem];return tile.ItemName+"\n"+categories[selectedGroup]+"   /   "+(!tile.Known?"WAITING FOR GAME":tile.Owned?"OWNED":"MISSING")+(tile.Artwork==null?"   /   Image unavailable":"");}}
        internal InventoryCanvas() {
            DoubleBuffered=true;AutoScroll=true;WrapContents=false;FlowDirection=FlowDirection.TopDown;Padding=new Padding(12,10,0,12);BackColor=ToolColors.Background;
            Color[] accents={Color.FromArgb(117,172,245),Color.FromArgb(112,204,166),Color.FromArgb(255,200,114)};
            for(int group=0;group<3;group++) {
                int category=group;string[] names=group==0?weapons:group==1?Array.ConvertAll(itemIds,Item):parts;
                var panel=new FlowLayoutPanel{FlowDirection=FlowDirection.LeftToRight,WrapContents=true,Padding=new Padding(5),Margin=new Padding(0,0,0,10),BackColor=group==0?Color.FromArgb(15,25,42):group==1?Color.FromArgb(13,29,27):Color.FromArgb(30,25,18)};
                var heading=new Label{UseMnemonic=false,Height=28,ForeColor=accents[group],Padding=new Padding(3,5,0,0),Font=new Font(Font,FontStyle.Bold)};panel.Controls.Add(heading);headings.Add(heading);
                var buttons=new InventoryTile[names.Length];
                for(int i=0;i<names.Length;i++) {
                    int item=i;var button=new InventoryTile{ItemName=names[i],Accent=accents[group],AccessibleName=names[i]};buttons[i]=button;panel.Controls.Add(button);
                    button.Click+=delegate{selectedGroup=category;selectedItem=item;RefreshTiles();if(SelectionChanged!=null)SelectionChanged();};
                }
                tiles.Add(buttons);Controls.Add(panel);
            }
            SizeChanged+=delegate{LayoutGroups();};RefreshTiles();
        }
        private void LayoutGroups() {
            int width=Math.Max(300,ClientSize.Width-Padding.Horizontal-SystemInformation.VerticalScrollBarWidth-3);
            for(int g=0;g<3;g++) {var panel=Controls[g];panel.Width=width;headings[g].Width=width-16;int columns=Math.Max(1,(width-10)/60);panel.Height=38+((tiles[g].Length+columns-1)/columns)*60;}
        }
        internal void SetImages(Dictionary<int,Bitmap> images){
            for(int g=0;g<tiles.Count;g++)for(int i=0;i<tiles[g].Length;i++){int key=g==0?i:g==1?100+itemIds[i]:200+i;Bitmap image;if(images.TryGetValue(key,out image))tiles[g][i].Artwork=image;}
            Invalidate(true);if(SelectionChanged!=null)SelectionChanged();
        }
        internal void RefreshTiles() {
            for(int group=0;group<3;group++) {
                int owned=0;
                for(int i=0;i<tiles[group].Length;i++) {
                    var tile=tiles[group][i];tile.Known=Value!=null&&(group!=1||itemIds[i]<Value.items.Length)&&(group!=2||Shared!=null&&i<Shared.Length);
                    tile.Owned=Value!=null&&(group==0?(Value.weapons&(1<<i))!=0:group==1?itemIds[i]<Value.items.Length&&Value.items[itemIds[i]]:Shared!=null&&i<Shared.Length&&Shared[i]);
                    if(tile.Owned)owned++;tile.Selected=group==selectedGroup&&i==selectedItem;
                    string description=tile.ItemName+" - "+(!tile.Known?"unknown":tile.Owned?"owned":"missing");
                    tile.AccessibleDescription=description;tips.SetToolTip(tile,description);tile.Invalidate();
                }
                headings[group].Text=categories[group]+"    "+(Value==null?"--":owned.ToString())+" / "+tiles[group].Length;
            }
        }
        internal static string Item(int id) {
            switch(id){case 0:return "Yellow key";case 1:return "Red key";case 2:return "Magenta key";case 3:return "Green key";case 9:return "Blue key";case 10:return "Tri-rocket flag";case 16:return "Specialist magazine";case 17:return "Mine key";case 20:return "Pants";case 21:return "Crowbar";case 22:return "Night vision goggles";case 23:return "Gold bar 3";case 24:return "Gold bar 2";case 25:return "Gold bar 1";case 26:return "Ear plugs";case 27:return "Arcade chip";default:return "Unmapped bit "+id;}
        }
        protected override void Dispose(bool disposing){if(disposing)tips.Dispose();base.Dispose(disposing);}
    }
}
