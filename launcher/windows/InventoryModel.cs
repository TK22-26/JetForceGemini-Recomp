using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
namespace JfgLauncher {
    // Small deterministic thumbnail renderer for static pickup models. It reads
    // the ROM's vertices, triangle batches, UVs and textures; it does not capture
    // gameplay, modify a save, or ship a pre-rendered image.
    internal static class InventoryModel {
        private const int Size=128;
        private static void Require(byte[] data,int offset,int length) {
            if(offset<0||length<0||offset>data.Length-length)throw new InvalidDataException("Invalid item model range.");
        }
        private static int U16(byte[] data,int p){Require(data,p,2);return data[p]<<8|data[p+1];}
        private static int S16(byte[] data,int p){return (short)U16(data,p);}
        private static int U32(byte[] data,int p){Require(data,p,4);uint v=(uint)(data[p]<<24|data[p+1]<<16|data[p+2]<<8|data[p+3]);if(v>Int32.MaxValue)throw new InvalidDataException("Invalid model offset.");return (int)v;}
        private sealed class Material {
            internal int Width,Height;internal Color[] Pixels;
            internal Material(Bitmap image){Width=image.Width;Height=image.Height;Pixels=new Color[Width*Height];for(int y=0;y<Height;y++)for(int x=0;x<Width;x++)Pixels[y*Width+x]=image.GetPixel(x,y);}
            internal Color Sample(double u,double v){int x=((int)Math.Floor(u)%Width+Width)%Width,y=((int)Math.Floor(v)%Height+Height)%Height;return Pixels[y*Width+x];}
        }
        internal static Bitmap Render(byte[] data,Func<int,Bitmap> texture,int group=-1) {
            Require(data,0,136);int nv=U16(data,18),nt=U16(data,20),nb=U16(data,22),materials=data[16];
            if(nv<3||nv>4096||nt<1||nt>8192||nb<1||nb>1024)throw new InvalidDataException("Unsupported item model size.");
            int tp=U32(data,24),vp=U32(data,28),fp=U32(data,32),bp=U32(data,36);
            Require(data,tp,materials*8);Require(data,vp,nv*10);Require(data,fp,nt*16);Require(data,bp,(nb+1)*16);
            var textures=new Dictionary<int,Material>();var vertices=new double[nv,3];var used=new bool[nv];
            // Some menu models contain independent display groups far apart.
            // Fit only vertices referenced by the requested group.
            for(int batch=0;batch<nb;batch++) {
                int p=bp+batch*16;if(group>=0&&data[p+1]!=group)continue;
                int first=U16(data,p+8),end=U16(data,p+24),vertexBase=U16(data,p+6);
                if(first>end||end>nt)throw new InvalidDataException("Invalid model triangle batch.");
                for(int t=first;t<end;t++)for(int corner=1;corner<=3;corner++) {
                    int index=vertexBase+data[fp+t*16+corner];if(index>=nv)throw new InvalidDataException("Invalid model vertex index.");used[index]=true;
                }
            }
            double left=Double.MaxValue,top=Double.MaxValue,right=Double.MinValue,bottom=Double.MinValue;
            for(int i=0;i<nv;i++) {
                int p=vp+i*10;double x=S16(data,p),y=S16(data,p+2),z=S16(data,p+4);
                double xx=x*.8660254+z*.5,zz=-x*.5+z*.8660254;
                vertices[i,0]=xx;vertices[i,1]=-(y*.9396926-zz*.3420201);vertices[i,2]=y*.3420201+zz*.9396926;
                if(used[i]){left=Math.Min(left,vertices[i,0]);right=Math.Max(right,vertices[i,0]);top=Math.Min(top,vertices[i,1]);bottom=Math.Max(bottom,vertices[i,1]);}
            }
            if(left==Double.MaxValue)throw new InvalidDataException("Empty model display group.");
            double scale=104/Math.Max(1,Math.Max(right-left,bottom-top));
            for(int i=0;i<nv;i++){vertices[i,0]=(vertices[i,0]-(left+right)/2)*scale+64;vertices[i,1]=(vertices[i,1]-(top+bottom)/2)*scale+64;}
            var pixels=new Color[Size*Size];var depth=new double[pixels.Length];for(int i=0;i<depth.Length;i++)depth[i]=Double.MinValue;
            for(int batch=0;batch<nb;batch++) {
                int p=bp+batch*16,material=data[p],vertexBase=U16(data,p+6),first=U16(data,p+8),end=U16(data,p+24);
                if(group>=0&&data[p+1]!=group)continue;
                if(first>end||end>nt)throw new InvalidDataException("Invalid model triangle batch.");
                Material tex=null;
                if(material!=255) {
                    if(material>=materials)throw new InvalidDataException("Invalid model material.");
                    if(!textures.TryGetValue(material,out tex)) {
                        using(var image=texture(U16(data,tp+material*8+6)))tex=new Material(image);textures.Add(material,tex);
                    }
                }
                for(int t=first;t<end;t++) {
                    int face=fp+t*16,a=vertexBase+data[face+1],b=vertexBase+data[face+2],c=vertexBase+data[face+3];
                    if(a>=nv||b>=nv||c>=nv)throw new InvalidDataException("Invalid model vertex index.");
                    double ax=vertices[a,0],ay=vertices[a,1],bx=vertices[b,0],by=vertices[b,1],cx=vertices[c,0],cy=vertices[c,1];
                    double denominator=(by-cy)*(ax-cx)+(cx-bx)*(ay-cy);if(Math.Abs(denominator)<.001)continue;
                    double au=S16(data,face+4)/32.0,av=S16(data,face+6)/32.0,bu=S16(data,face+8)/32.0,bv=S16(data,face+10)/32.0,cu=S16(data,face+12)/32.0,cv=S16(data,face+14)/32.0;
                    int x0=Math.Max(0,(int)Math.Floor(Math.Min(ax,Math.Min(bx,cx)))),x1=Math.Min(Size,(int)Math.Ceiling(Math.Max(ax,Math.Max(bx,cx))));
                    int y0=Math.Max(0,(int)Math.Floor(Math.Min(ay,Math.Min(by,cy)))),y1=Math.Min(Size,(int)Math.Ceiling(Math.Max(ay,Math.Max(by,cy))));
                    for(int y=y0;y<y1;y++)for(int x=x0;x<x1;x++) {
                        double wa=((by-cy)*(x+.5-cx)+(cx-bx)*(y+.5-cy))/denominator,wb=((cy-ay)*(x+.5-cx)+(ax-cx)*(y+.5-cy))/denominator,wc=1-wa-wb;
                        if(wa<0||wb<0||wc<0)continue;
                        double z=wa*vertices[a,2]+wb*vertices[b,2]+wc*vertices[c,2];int at=y*Size+x;if(z<=depth[at])continue;
                        Color color=tex==null?Color.FromArgb(218,225,235):tex.Sample(wa*au+wb*bu+wc*cu,wa*av+wb*bv+wc*cv);
                        if(color.A<16)continue;pixels[at]=color;depth[at]=z;
                    }
                }
            }
            var result=new Bitmap(Size,Size,PixelFormat.Format32bppArgb);
            try {for(int y=0;y<Size;y++)for(int x=0;x<Size;x++)result.SetPixel(x,y,pixels[y*Size+x]);return result;}
            catch{result.Dispose();throw;}
        }
    }
}
