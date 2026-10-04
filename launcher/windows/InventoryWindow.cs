using System;
using System.Drawing;
using System.IO;
using System.Runtime.Serialization;
using System.Runtime.Serialization.Json;
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
                if(c==null||c.id<0||c.id>2||seen[c.id]||c.weapons<0||c.weapons>65535||c.items==null||c.items.Length!=27)
                    throw new InvalidDataException("Invalid character inventory.");
                seen[c.id]=true;
            }
        }
    }
    internal sealed class InventoryWindow:Form {
        private string directory;
        private readonly TabControl tabs=new TabControl{Dock=DockStyle.Fill};
        private readonly CheckBox follow=new CheckBox{Text="Follow active character",Checked=true,AutoSize=true};
        private readonly Label status=new Label{AutoSize=true,Padding=new Padding(12,5,0,0)};
        private readonly Timer timer=new Timer{Interval=500};
        private readonly InventoryCanvas[] canvases=new InventoryCanvas[3];
        private int current=-1;
        internal int SelectedCharacter {get{return new[]{1,0,2}[tabs.SelectedIndex];}}
        internal InventoryWindow(string path) {
            directory=path;Text="JFG Live Inventory";ClientSize=new Size(760,680);MinimumSize=new Size(530,430);
            Font=new Font("Segoe UI",9);BackColor=Color.FromArgb(15,25,34);ForeColor=Color.White;
            var bar=new FlowLayoutPanel{Dock=DockStyle.Top,Height=34,Padding=new Padding(8,4,0,0)};
            bar.Controls.Add(follow);bar.Controls.Add(status);
            // Supported game enum: Vela=0, Juno=1, Lupus=2.
            string[] names={"Vela","Juno","Lupus"};
            foreach(int id in new[]{1,0,2}) {
                var page=new TabPage(names[id]){BackColor=BackColor};
                canvases[id]=new InventoryCanvas{Dock=DockStyle.Fill};page.Controls.Add(canvases[id]);tabs.TabPages.Add(page);
            }
            Controls.Add(tabs);Controls.Add(bar);
            follow.CheckedChanged+=delegate{if(follow.Checked&&current>=0)tabs.SelectedIndex=current==1?0:current==0?1:2;};
            timer.Tick+=delegate{RefreshInventory();};Shown+=delegate{RefreshInventory();timer.Start();};
            FormClosed+=delegate{timer.Stop();timer.Dispose();};
        }
        internal void BindDirectory(string path){directory=path;current=-1;RefreshInventory();}
        internal void Apply(InventoryTracker value,bool live) {
            if(value==null||!value.known) {
                status.Text="Waiting for gameplay inventory...";
                foreach(var canvas in canvases){canvas.Value=null;canvas.Invalidate();}
                current=-1;return;
            }
            value.Validate();
            if(current!=value.current&&follow.Checked)tabs.SelectedIndex=value.current==1?0:value.current==0?1:2;
            current=value.current;status.Text=live?"LIVE  •  Bright: owned   Dim: missing":"Saved snapshot • game closed or paused";
            foreach(var c in value.characters){canvases[c.id].Value=c;canvases[c.id].Shared=value.shared;canvases[c.id].Invalidate();}
        }
        private void RefreshInventory() {
            try {
                using(var file=new FileStream(Path.Combine(directory,"live.json"),FileMode.Open,FileAccess.Read,FileShare.ReadWrite|FileShare.Delete)) {
                    if(file.Length>16*1024*1024)throw new InvalidDataException("Inventory export is too large.");
                    var live=(MapLive)new DataContractJsonSerializer(typeof(MapLive)).ReadObject(file);
                    if(live==null||live.schema!=1)throw new InvalidDataException("Unsupported inventory export.");
                    long age=NavigationExplorer.Clock-live.timestamp_ms;
                    Apply(live.inventory_tracker,age>=0&&age<5000);
                }
            }catch(Exception error) {
                if(!(error is IOException)&&!(error is UnauthorizedAccessException)&&!(error is SerializationException))throw;
                status.Text=error.Message;foreach(var canvas in canvases){canvas.Value=null;canvas.Invalidate();}
            }
        }
    }
    internal sealed class InventoryCanvas:ScrollableControl {
        internal CharacterInventory Value;
        internal bool[] Shared;
        private static readonly string[] weapons={"Pistol","Homing missiles","Machine gun","Shotgun","Shrink ray","Rocket launcher","Flamethrower","Grenades","Shurikens","Fish food","Proximity mines","Timed mines","Remote mines","Flares","Cluster bombs"};
        private static readonly string[] parts={"Power cell","Radar dish","Fin","Cargo bay key","Deflector shield","Ship part 37","Ship part 38","Ship part 39","Ship part 40","Ship part 41","Ship part 42","Stabilizer"};
        internal InventoryCanvas(){DoubleBuffered=true;AutoScroll=true;BackColor=Color.FromArgb(15,25,34);}
        private static string Item(int id) {
            switch(id){case 1:return "Red key";case 16:return "Miner magazine";case 17:return "Mine key";case 20:return "Pants";case 21:return "Crowbar";case 22:return "Night vision";case 23:return "Gold coin 1";case 24:return "Gold coin 2";case 25:return "Gold coin 3";default:return "Item "+id+" (unidentified)";}
        }
        protected override void OnPaint(PaintEventArgs e) {
            base.OnPaint(e);var g=e.Graphics;
            int columns=Math.Max(3,(ClientSize.Width-28)/138),width=Math.Max(100,(ClientSize.Width-28)/columns),y=16+AutoScrollPosition.Y;
            if(Value==null){TextRenderer.DrawText(g,"Inventory appears when a game is loaded.",Font,new Point(16,y),Color.Silver);return;}
            DrawGroup(g,"WEAPONS",weapons,delegate(int i){return (Value.weapons&(1<<i))!=0;},columns,width,ref y);
            var labels=new string[27];for(int i=0;i<labels.Length;i++)labels[i]=Item(i);
            DrawGroup(g,"KEYS & QUEST ITEMS",labels,delegate(int i){return Value.items[i];},columns,width,ref y);
            DrawGroup(g,"SHIP PARTS · SHARED",parts,delegate(int i){return Shared!=null&&Shared[i];},columns,width,ref y);
            int height=y-AutoScrollPosition.Y;
            if(AutoScrollMinSize.Height!=height)AutoScrollMinSize=new Size(0,height);
        }
        private void DrawGroup(Graphics g,string heading,string[] names,Func<int,bool> owned,int columns,int width,ref int y) {
            TextRenderer.DrawText(g,heading,Font,new Point(12,y),Color.FromArgb(90,215,223));y+=28;
            for(int i=0;i<names.Length;i++) {
                int x=12+(i%columns)*width,top=y+(i/columns)*64;bool has=owned(i);
                var rect=new Rectangle(x,top,width-8,56);
                using(var brush=new SolidBrush(has?Color.FromArgb(29,91,104):Color.FromArgb(24,36,47)))g.FillRectangle(brush,rect);
                using(var pen=new Pen(has?Color.FromArgb(96,224,203):Color.FromArgb(49,62,73)))g.DrawRectangle(pen,rect);
                TextRenderer.DrawText(g,(has?"✓ ":"· ")+names[i],Font,new Rectangle(x+7,top+6,width-22,44),
                    has?Color.White:Color.FromArgb(125,141,154),TextFormatFlags.WordBreak|TextFormatFlags.VerticalCenter);
            }
            y+=((names.Length+columns-1)/columns)*64+14;
        }
    }
}
