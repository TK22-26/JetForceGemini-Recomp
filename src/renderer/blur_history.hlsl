struct Constants { float alpha; float3 padding; };
[[vk::push_constant]] ConstantBuffer<Constants> gConstants : register(b0);
Texture2D<float4> gPrevious : register(t1);
Texture2D<float4> gCurrent : register(t2);
float4 PSMain(float4 position : SV_Position) : SV_TARGET {
    uint2 pixel = uint2(position.xy);
    return lerp(gPrevious.Load(uint3(pixel, 0)), gCurrent.Load(uint3(pixel, 0)), gConstants.alpha);
}
