// Per-actor downward depth maps, generated from presentation pose endpoints.
// No native mask sampling, CPU readback, or temporal image crossfade.
struct ShadowVertex { float3 current; uint source; float3 previous; float opacity; float previous_opacity; float3 padding; };
struct Constants { float4 bounds; float4 screen; float4 light; float alpha; uint first; uint receiverFirst; uint receiverCount; float4 proxyCurrent; float4 proxyPrevious; float4 proxyShape; };
struct FramebufferParams { float2 resolution; float2 resolutionScale; float horizontalMisalignment; };
[[vk::push_constant]] ConstantBuffer<Constants> C : register(b0);
StructuredBuffer<ShadowVertex> Vertices : register(t1);
Texture2D<float> HeightMap : register(t2);
StructuredBuffer<float4> ScreenPositions : register(t3);
ConstantBuffer<FramebufferParams> Framebuffer : register(b4);
struct MaskVarying { float4 position : SV_Position; float height : TEXCOORD0; };
MaskVarying MaskVS(uint id : SV_VertexID) {
    if(C.proxyShape.z>0) {
        const float2 corners[6]={float2(-1,1),float2(1,1),float2(-1,-1),
                                float2(-1,-1),float2(1,1),float2(1,-1)};
        MaskVarying o;o.position=float4(corners[id],0.5,1);o.height=0;return o;
    }
    ShadowVertex v=Vertices[C.first+id];
    float3 p=lerp(v.previous,v.current,C.alpha);
    float2 uv=(p.xz+p.y*lerp(C.light.zw,C.light.xy,C.alpha)-C.bounds.xy)*C.bounds.w;
    MaskVarying o;
    o.position=float4(uv.x*2-1,1-uv.y*2,0.5,1);
    o.height=p.y;return o;
}
float MaskPS(MaskVarying i) : SV_Target {
    if(C.proxyShape.z>0) {
        // Analytic light-ray/ellipsoid intersection for native sprite objects.
        // Work relative to the center to avoid cancellation in distant rooms.
        float4 sphere=lerp(C.proxyPrevious,C.proxyCurrent,C.alpha);
        float vertical=lerp(C.proxyShape.y,C.proxyShape.x,C.alpha);
        float2 light=lerp(C.light.zw,C.light.xy,C.alpha);
        float2 projected=C.bounds.xy+(i.position.xy/512)*C.bounds.z;
        float2 delta=projected-sphere.xz-sphere.y*light;
        float invHorizontal=rcp(sphere.w*sphere.w);
        float a=dot(light,light)*invHorizontal+rcp(vertical*vertical);
        float b=-2*dot(delta,light)*invHorizontal;
        float c=dot(delta,delta)*invHorizontal-1;
        float discriminant=b*b-4*a*c;
        if(discriminant<0)discard;
        return sphere.y+(-b+sqrt(discriminant))/(2*a);
    }
    return i.height;
}
struct ReceiverVarying { float4 position : SV_Position; float3 world : TEXCOORD0; float opacity : TEXCOORD1; };
ReceiverVarying ReceiverVS(uint id : SV_VertexID) {
    ShadowVertex v=Vertices[C.first+id];
    float4 p=ScreenPositions[v.source];
    p.xy-=Framebuffer.resolution*0.5;
    p.xy/=Framebuffer.resolution*float2(0.5,-0.5);
    p.xyz*=p.w;
    p.xy=p.xy*C.screen.xy+C.screen.zw*p.w;
    ReceiverVarying o;o.position=p;
    o.world=lerp(v.previous,v.current,C.alpha);o.opacity=lerp(v.previous_opacity,v.opacity,C.alpha);return o;
}

// Return the first receiving surface above this point along the light ray.
// Exact triangle intersections preserve platform edges at sub-texel precision.
// Y/Z store the upper surface's plane slope in light-space world units.
float cross2(float2 a,float2 b) { return a.x*b.y-a.y*b.x; }
float3 nextReceiver(float3 world,float2 light) {
    float3 result=float3(1e9,0,0);
    [loop] for(uint n=0;n+2<C.receiverCount;n+=3) {
        ShadowVertex va=Vertices[C.receiverFirst+n];
        ShadowVertex vb=Vertices[C.receiverFirst+n+1];
        ShadowVertex vc=Vertices[C.receiverFirst+n+2];
        float3 a=lerp(va.previous,va.current,C.alpha);
        float3 b=lerp(vb.previous,vb.current,C.alpha);
        float3 c=lerp(vc.previous,vc.current,C.alpha);
        float2 pa=(a.xz-world.xz)+(a.y-world.y)*light;
        float2 ab=(b.xz-a.xz)+(b.y-a.y)*light;
        float2 ac=(c.xz-a.xz)+(c.y-a.y)*light;
        float det=cross2(ab,ac);
        if(abs(det)<1e-7)continue;
        float u=cross2(-pa,ac)/det,v=cross2(ab,-pa)/det;
        if(u < -1e-5 || v < -1e-5 || u+v>1.00001)continue;
        float h=a.y+u*(b.y-a.y)+v*(c.y-a.y);
        if(h<=world.y+0.05 || h>=result.x)continue;
        result=float3(h,((b.y-a.y)*ac.y-(c.y-a.y)*ab.y)/det,
            ((c.y-a.y)*ab.x-(b.y-a.y)*ac.x)/det);
    }
    return result;
}
float compareAt(int2 cell,float2 center,float height,float2 gradient,float3 upper) {
    if(any(cell<0)||any(cell>=512))return 0;
    float2 delta=float2(cell)-center;
    float floorHeight=height+dot(gradient,delta);
    float upperHeight=upper.x+dot(upper.yz,delta);
    float caster=HeightMap.Load(int3(cell,0));
    return caster>floorHeight+0.05 && caster<upperHeight-0.05 ? 1.0 : 0.0;
}
float filteredComparison(float2 pixel,float2 center,float height,float2 gradient,float3 upper) {
    int2 base=int2(floor(pixel));float2 w=frac(pixel);
    return lerp(lerp(compareAt(base,center,height,gradient,upper),
                     compareAt(base+int2(1,0),center,height,gradient,upper),w.x),
                lerp(compareAt(base+int2(0,1),center,height,gradient,upper),
                     compareAt(base+int2(1,1),center,height,gradient,upper),w.x),w.y);
}
// Bilinear blocker membership avoids a sudden radius change when a nearest
// search sample crosses an animated silhouette.
float2 blockerAt(float2 pixel,float2 center,float height,float2 gradient,float3 upper) {
    int2 base=int2(floor(pixel));float2 w=frac(pixel);float2 sum=0;
    [unroll] for(int y=0;y<2;++y)[unroll] for(int x=0;x<2;++x) {
        int2 q=base+int2(x,y);
        if(any(q<0)||any(q>=512))continue;
        float2 delta=float2(q)-center;
        float floorHeight=height+dot(gradient,delta);
        float caster=HeightMap.Load(int3(q,0));
        float upperHeight=upper.x+dot(upper.yz,delta);
        float weight=(x?w.x:1-w.x)*(y?w.y:1-w.y);
        if(caster>floorHeight+0.05 && caster<upperHeight-0.05)
            sum+=float2((caster-floorHeight)*weight,weight);
    }
    return sum;
}
float2 diskSample(uint index,uint count) {
    float angle=float(index)*2.399963229728653;
    return sqrt((float(index)+0.5)/float(count))*float2(cos(angle),sin(angle));
}
float4 ReceiverPS(ReceiverVarying i) : SV_Target {
    float2 light=lerp(C.light.zw,C.light.xy,C.alpha);
    float2 uv=(i.world.xz+i.world.y*light-C.bounds.xy)*C.bounds.w;
    if(any(uv<=0)||any(uv>=1))discard;
    float2 pixel=uv*512-0.5;
    float2 dx=ddx(uv),dy=ddy(uv);
    float hx=ddx(i.world.y),hy=ddy(i.world.y);
    float determinant=dx.x*dy.y-dx.y*dy.x;
    float2 gradient=abs(determinant)>1e-12
        ?float2(hx*dy.y-hy*dx.y,hy*dx.x-hx*dy.x)/(determinant*512):float2(0,0);
    float3 upper=nextReceiver(i.world,light);
    upper.yz*=C.bounds.z/512;
    float2 blockers=0;
    float searchRadius=4.0*512*C.bounds.w;
    [unroll] for(uint b=0;b<16;++b)
        blockers+=blockerAt(pixel+diskSample(b,16)*searchRadius,pixel,i.world.y,gradient,upper);
    float separation=blockers.x/max(blockers.y,1.0);
    // A small angular source retains contact detail. A dense disk avoids the
    // regular islands produced by stretching a sparse 5x5 square grid.
    float radius=clamp((0.12+separation*0.015)*512*C.bounds.w,0.75,8.0);
    float coverage=0;
    [unroll] for(uint s=0;s<32;++s)
        coverage+=filteredComparison(pixel+diskSample(s,32)*radius,pixel,i.world.y,gradient,upper);
    return float4(0,0,0,saturate(i.opacity)*0.5*(coverage/32));
}
