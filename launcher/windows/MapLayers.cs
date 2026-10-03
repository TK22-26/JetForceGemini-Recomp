using System;
using System.Collections.Generic;
using System.Drawing;

namespace JfgLauncher
{
    internal struct HeightPoint
    {
        internal float X, Y, Z;
        internal HeightPoint(float x, float y, float z) { X=x; Y=y; Z=z; }
        internal HeightPoint(float[] p) { X=p[0]; Y=p[1]; Z=p[2]; }
        internal static HeightPoint Lerp(HeightPoint a, HeightPoint b, float t) {
            return new HeightPoint(a.X+(b.X-a.X)*t, a.Y+(b.Y-a.Y)*t, a.Z+(b.Z-a.Z)*t);
        }
    }
    internal sealed class HeightSurface
    {
        internal HeightPoint[] Points;
        internal float Low, High;
        internal HeightSurface(HeightPoint[] points) {
            Points=points; Low=Single.MaxValue; High=Single.MinValue;
            foreach (HeightPoint p in points) { Low=Math.Min(Low,p.Y); High=Math.Max(High,p.Y); }
        }
    }
    internal sealed class HeightPatch
    {
        internal HeightSurface Surface;
        internal Color Color;
    }
    internal sealed class MapLayers
    {
        internal readonly List<HeightSurface> Floors = new List<HeightSurface>();
        internal readonly List<HeightPatch> Patches = new List<HeightPatch>();
        internal float Low, High;
        internal const int Bands=16;
        internal MapLayers(MapGeometry mesh) {
            Low=Single.MaxValue; High=Single.MinValue;
            foreach (MapFace face in mesh.triangles) {
                HeightPoint[] p=new HeightPoint[3];
                for(int i=0;i<3;i++) p[i]=new HeightPoint(mesh.vertices[face.v[i]]);
                double ux=p[1].X-p[0].X, uy=p[1].Y-p[0].Y, uz=p[1].Z-p[0].Z;
                double vx=p[2].X-p[0].X, vy=p[2].Y-p[0].Y, vz=p[2].Z-p[0].Z;
                double nx=uy*vz-uz*vy, ny=uz*vx-ux*vz, nz=ux*vy-uy*vx;
                double length=Math.Sqrt(nx*nx+ny*ny+nz*nz);
                if(length<.00001) continue;
                double normalY=ny/length;
                if(face.normal!=null) {
                    double magnitude=Math.Sqrt((double)face.normal[0]*face.normal[0]+(double)face.normal[1]*face.normal[1]+(double)face.normal[2]*face.normal[2]);
                    if(magnitude>.00001) normalY=face.normal[1]/magnitude;
                }
                // Upward surface candidates, not a walkability assertion.
                if(normalY<.35 || Math.Abs(ny)<.00001) continue;
                HeightSurface floor=new HeightSurface(p); Floors.Add(floor);
                Low=Math.Min(Low,floor.Low); High=Math.Max(High,floor.High);
            }
            if(Floors.Count==0) {Low=0;High=1;return;}
            if(High-Low<1) High=Low+1;
            foreach(HeightSurface floor in Floors) {
                int first=Band(floor.Low),last=Band(floor.High);
                for(int band=first;band<=last;band++) {
                    float low=Low+(High-Low)*band/Bands, high=Low+(High-Low)*(band+1)/Bands;
                    HeightPoint[] clipped=Clip(floor.Points,low,high);
                    if(clipped.Length>=3) Patches.Add(new HeightPatch { Surface=new HeightSurface(clipped),Color=HeightColor((band+.5f)/Bands) });
                }
            }
            Patches.Sort(delegate(HeightPatch a,HeightPatch b) {return (a.Surface.Low+a.Surface.High).CompareTo(b.Surface.Low+b.Surface.High);});
        }
        internal int Band(float y) {return Math.Max(0,Math.Min(Bands-1,(int)((y-Low)/(High-Low)*Bands)));}
        internal static Color HeightColor(float t) {
            Color[] stops={Color.FromArgb(62,45,102),Color.FromArgb(42,91,130),Color.FromArgb(31,139,138),Color.FromArgb(91,181,105),Color.FromArgb(223,222,80)};
            t=Math.Max(0,Math.Min(1,t))*4;
            int i=Math.Min(3,(int)t);float f=t-i;
            return Color.FromArgb((int)(stops[i].R+(stops[i+1].R-stops[i].R)*f),(int)(stops[i].G+(stops[i+1].G-stops[i].G)*f),(int)(stops[i].B+(stops[i+1].B-stops[i].B)*f));
        }
        private static HeightPoint[] HalfClip(HeightPoint[] input,float height,bool above) {
            if(input.Length==0) return input;
            List<HeightPoint> output=new List<HeightPoint>();
            HeightPoint a=input[input.Length-1];bool aInside=above?a.Y>=height:a.Y<=height;
            foreach(HeightPoint b in input) {
                bool bInside=above?b.Y>=height:b.Y<=height;
                if(aInside!=bInside) output.Add(HeightPoint.Lerp(a,b,(height-a.Y)/(b.Y-a.Y)));
                if(bInside) output.Add(b);
                a=b;aInside=bInside;
            }
            return output.ToArray();
        }
        // Clip edges in 3D before projection, retaining the visible parts of ramps.
        internal static HeightPoint[] Clip(HeightPoint[] input,float low,float high) {
            return HalfClip(HalfClip(input,low,true),high,false);
        }
        internal bool Support(HeightPoint point,out float height) {
            height=Single.MinValue;bool found=false;
            foreach(HeightSurface floor in Floors) {
                HeightPoint a=floor.Points[0],b=floor.Points[1],c=floor.Points[2];
                double den=(double)(b.Z-c.Z)*(a.X-c.X)+(double)(c.X-b.X)*(a.Z-c.Z);
                if(Math.Abs(den)<.00001) continue;
                double u=((double)(b.Z-c.Z)*(point.X-c.X)+(double)(c.X-b.X)*(point.Z-c.Z))/den;
                double v=((double)(c.Z-a.Z)*(point.X-c.X)+(double)(a.X-c.X)*(point.Z-c.Z))/den;
                if(u<-.0001 || v<-.0001 || u+v>1.0001) continue;
                float y=(float)(u*a.Y+v*b.Y+(1-u-v)*c.Y);
                if(y<=point.Y+4 && (!found || y>height)) {height=y;found=true;}
            }
            return found;
        }
    }
    internal sealed class FloorFollower
    {
        internal bool HasHeight, Grounded;
        internal float Height;
        internal void Update(MapLayers layers,HeightPoint player) {
            float ground;
            Grounded=layers.Support(player,out ground) && Math.Abs(player.Y-ground)<=8;
            if(Grounded) {Height=ground;HasHeight=true;}
            else if(!HasHeight) {Height=player.Y;HasHeight=true;}
        }
    }
}
