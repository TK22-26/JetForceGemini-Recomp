// Tests call the production shader against analytic surfaces and depth values.
#include "enhanced_shadow.hlsl"
RWStructuredBuffer<float4> Results : register(u6);
[numthreads(1,1,1)] void Check(uint3 id:SV_DispatchThreadID) {
 float shift=lerp(-2.0,0.0,C.alpha);
 float3 none=float3(1e9,0,0); float4 value=0;
 switch(id.x) {
 case 0:value=float4(nextReceiver(float3(shift-.001,0,0),0),0);break;
 case 1:value=float4(nextReceiver(float3(shift+.001,0,0),0),0);break;
 case 2:value=float4(nextReceiver(float3(shift+5,0,0),0),0);break;
 case 3:value=float4(nextReceiver(float3(shift+5,6,0),0),0);break;
 case 4:value=float4(nextReceiver(float3(shift+3,0,0),float2(.5,0)),0);break;
 case 5:value=float4(nextReceiver(float3(shift+5,9,0),0),0);break;
 case 6:value.x=compareAt(int2(250,250),float2(250,250),0,0,float3(8,0,0));break;
 case 7:value.x=compareAt(int2(250,250),float2(250,250),0,0,float3(12,0,0));break;
 case 8:value.x=compareAt(int2(250,250),float2(220,250),0,float2(.5,0),none);break;
 case 9:value.x=filteredComparison(float2(255.25,250),float2(255.25,250),0,0,none);break;
 case 10:value.x=filteredComparison(float2(255.5,250),float2(255.5,250),0,0,none);break;
 case 11:value.x=filteredComparison(float2(255.75,250),float2(255.75,250),0,0,none);break;
 case 12:value.xy=blockerAt(float2(255.25,250),float2(255.25,250),0,0,none);break;
 case 13:value.x=compareAt(int2(512,250),float2(512,250),0,0,none);break;
 case 14:value=float4(nextReceiver(float3(shift+5,5.25,0),0),0);break;
 case 15:value=float4(nextReceiver(float3(shift+10.001,0,0),0),0);break;
 }
 Results[id.x]=value;
}
