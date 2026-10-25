// Composite the depth-resolved character once. Native framebuffer coverage is unchanged.
struct FadeParams { float opacity; float3 padding; };
[[vk::push_constant]] ConstantBuffer<FadeParams> fade : register(b0);
#ifdef MULTISAMPLING
Texture2DMS<float4> layer : register(t1);
float4 PSMain(float4 pos : SV_Position, uint sampleIndex : SV_SampleIndex) : SV_TARGET {
    return float4(layer.Load(int2(pos.xy), sampleIndex).rgb, fade.opacity);
}
#else
Texture2D<float4> layer : register(t1);
float4 PSMain(float4 pos : SV_Position) : SV_TARGET {
    return float4(layer.Load(int3(int2(pos.xy), 0)).rgb, fade.opacity);
}
#endif
