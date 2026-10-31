// Standalone D3D12 WARP qualification; no ROM, game or display is required.
#include <windows.h>
#include <d3d12.h>
#include <dxgi1_4.h>
#include <wrl/client.h>
#include <array>
#include <vector>
#include <fstream>
#include <iterator>
#include <cstring>
#include <cmath>
#include <cstdio>
#include <stdexcept>
using Microsoft::WRL::ComPtr;
void ok(HRESULT hr) { if(FAILED(hr)){std::fprintf(stderr,"HRESULT %08lx\n",hr);throw std::runtime_error("D3D12 check failed");}}
struct Vertex {float current[3];unsigned source;float previous[3];float opacity;float oldOpacity;float padding[3];};
static_assert(sizeof(Vertex)==48);
struct Params {float bounds[4],screen[4],light[4];float alpha;unsigned first,receiverFirst,receiverCount;float proxy[12];};
static_assert(sizeof(Params)==112);
int main(int argc,char** argv) {try {
 ComPtr<ID3D12Debug> debug;if(SUCCEEDED(D3D12GetDebugInterface(IID_PPV_ARGS(&debug))))debug->EnableDebugLayer();
 ComPtr<IDXGIFactory4> factory;ok(CreateDXGIFactory1(IID_PPV_ARGS(&factory)));
 ComPtr<IDXGIAdapter> warp;ok(factory->EnumWarpAdapter(IID_PPV_ARGS(&warp)));
 ComPtr<ID3D12Device> d;ok(D3D12CreateDevice(warp.Get(),D3D_FEATURE_LEVEL_11_0,IID_PPV_ARGS(&d)));
 D3D12_COMMAND_QUEUE_DESC qd{};qd.Type=D3D12_COMMAND_LIST_TYPE_DIRECT;
 ComPtr<ID3D12CommandQueue> queue;ok(d->CreateCommandQueue(&qd,IID_PPV_ARGS(&queue)));
 ComPtr<ID3D12CommandAllocator> alloc;ok(d->CreateCommandAllocator(qd.Type,IID_PPV_ARGS(&alloc)));
 ComPtr<ID3D12GraphicsCommandList> cmd;ok(d->CreateCommandList(0,qd.Type,alloc.Get(),nullptr,IID_PPV_ARGS(&cmd)));
 auto buffer=[&](size_t bytes,D3D12_HEAP_TYPE type,D3D12_RESOURCE_STATES state,D3D12_RESOURCE_FLAGS flags=D3D12_RESOURCE_FLAG_NONE) {
  D3D12_HEAP_PROPERTIES hp{};hp.Type=type;
  D3D12_RESOURCE_DESC rd{};rd.Dimension=D3D12_RESOURCE_DIMENSION_BUFFER;rd.Width=bytes;rd.Height=1;rd.DepthOrArraySize=1;rd.MipLevels=1;rd.SampleDesc.Count=1;rd.Layout=D3D12_TEXTURE_LAYOUT_ROW_MAJOR;rd.Flags=flags;
  ComPtr<ID3D12Resource> result;ok(d->CreateCommittedResource(&hp,D3D12_HEAP_FLAG_NONE,&rd,state,nullptr,IID_PPV_ARGS(&result)));return result;
 };
 std::vector<Vertex> vertices;
 auto rect=[&](float lo,float hi,float y,float slope) {
  const std::array<std::array<float,2>,6> points={{{lo,-8},{hi,-8},{lo,8},{lo,8},{hi,-8},{hi,8}}};
  for(auto p:points) {Vertex v{};v.current[0]=p[0];v.current[1]=y+slope*p[0];v.current[2]=p[1];std::memcpy(v.previous,v.current,12);v.previous[0]-=2;vertices.push_back(v);}
 };
 rect(-16,16,0,0);rect(0,10,4,.25);rect(0,10,8,0);
 auto vertex=buffer(vertices.size()*48,D3D12_HEAP_TYPE_UPLOAD,D3D12_RESOURCE_STATE_GENERIC_READ);
 void* mapped;D3D12_RANGE empty{0,0};ok(vertex->Map(0,&empty,&mapped));std::memcpy(mapped,vertices.data(),vertices.size()*48);vertex->Unmap(0,nullptr);
 D3D12_HEAP_PROPERTIES hp{};hp.Type=D3D12_HEAP_TYPE_DEFAULT;
 D3D12_RESOURCE_DESC td{};td.Dimension=D3D12_RESOURCE_DIMENSION_TEXTURE2D;td.Width=512;td.Height=512;td.DepthOrArraySize=1;td.MipLevels=1;td.Format=DXGI_FORMAT_R32_FLOAT;td.SampleDesc.Count=1;
 ComPtr<ID3D12Resource> texture;ok(d->CreateCommittedResource(&hp,D3D12_HEAP_FLAG_NONE,&td,D3D12_RESOURCE_STATE_COPY_DEST,nullptr,IID_PPV_ARGS(&texture)));
 D3D12_PLACED_SUBRESOURCE_FOOTPRINT footprint{};UINT64 uploadSize;d->GetCopyableFootprints(&td,0,1,0,&footprint,nullptr,nullptr,&uploadSize);
 auto upload=buffer(uploadSize,D3D12_HEAP_TYPE_UPLOAD,D3D12_RESOURCE_STATE_GENERIC_READ);
 ok(upload->Map(0,&empty,&mapped));for(unsigned y=0;y<512;++y)for(unsigned x=0;x<512;++x)reinterpret_cast<float*>(static_cast<char*>(mapped)+y*footprint.Footprint.RowPitch)[x]=x<256?10.0f:-1e9f;upload->Unmap(0,nullptr);
 D3D12_TEXTURE_COPY_LOCATION dest{};dest.pResource=texture.Get();dest.Type=D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
 D3D12_TEXTURE_COPY_LOCATION src{};src.pResource=upload.Get();src.Type=D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT;src.PlacedFootprint=footprint;
 cmd->CopyTextureRegion(&dest,0,0,0,&src,nullptr);
 auto barrier=[&](ID3D12Resource* r,D3D12_RESOURCE_STATES before,D3D12_RESOURCE_STATES after){D3D12_RESOURCE_BARRIER b{};b.Type=D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;b.Transition.pResource=r;b.Transition.StateBefore=before;b.Transition.StateAfter=after;b.Transition.Subresource=D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;cmd->ResourceBarrier(1,&b);};
 barrier(texture.Get(),D3D12_RESOURCE_STATE_COPY_DEST,D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE);
 D3D12_DESCRIPTOR_HEAP_DESC hd{};hd.Type=D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV;hd.NumDescriptors=2;hd.Flags=D3D12_DESCRIPTOR_HEAP_FLAG_SHADER_VISIBLE;
 ComPtr<ID3D12DescriptorHeap> heap;ok(d->CreateDescriptorHeap(&hd,IID_PPV_ARGS(&heap)));
 auto handle=heap->GetCPUDescriptorHandleForHeapStart();
 D3D12_SHADER_RESOURCE_VIEW_DESC sv{};sv.Shader4ComponentMapping=D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;sv.ViewDimension=D3D12_SRV_DIMENSION_BUFFER;sv.Buffer.NumElements=static_cast<UINT>(vertices.size());sv.Buffer.StructureByteStride=48;
 d->CreateShaderResourceView(vertex.Get(),&sv,handle);handle.ptr+=d->GetDescriptorHandleIncrementSize(hd.Type);
 sv={};sv.Shader4ComponentMapping=D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;sv.ViewDimension=D3D12_SRV_DIMENSION_TEXTURE2D;sv.Format=DXGI_FORMAT_R32_FLOAT;sv.Texture2D.MipLevels=1;d->CreateShaderResourceView(texture.Get(),&sv,handle);
 D3D12_DESCRIPTOR_RANGE range{};range.RangeType=D3D12_DESCRIPTOR_RANGE_TYPE_SRV;range.NumDescriptors=2;range.BaseShaderRegister=1;
 D3D12_ROOT_PARAMETER rp[3]{};rp[0].ParameterType=D3D12_ROOT_PARAMETER_TYPE_32BIT_CONSTANTS;rp[0].Constants.Num32BitValues=28;
 rp[1].ParameterType=D3D12_ROOT_PARAMETER_TYPE_DESCRIPTOR_TABLE;rp[1].DescriptorTable.NumDescriptorRanges=1;rp[1].DescriptorTable.pDescriptorRanges=&range;
 rp[2].ParameterType=D3D12_ROOT_PARAMETER_TYPE_UAV;rp[2].Descriptor.ShaderRegister=6;
 D3D12_ROOT_SIGNATURE_DESC rs{};rs.NumParameters=3;rs.pParameters=rp;
 ComPtr<ID3DBlob> blob,error;ok(D3D12SerializeRootSignature(&rs,D3D_ROOT_SIGNATURE_VERSION_1,&blob,&error));
 ComPtr<ID3D12RootSignature> signature;ok(d->CreateRootSignature(0,blob->GetBufferPointer(),blob->GetBufferSize(),IID_PPV_ARGS(&signature)));
 if(argc!=2)throw std::runtime_error("Expected compiled shader path");
 std::ifstream in(argv[1],std::ios::binary);std::vector<char> bytes((std::istreambuf_iterator<char>(in)),{});if(bytes.empty())throw std::runtime_error("Missing shader");
 D3D12_COMPUTE_PIPELINE_STATE_DESC pd{};pd.pRootSignature=signature.Get();pd.CS={bytes.data(),bytes.size()};
 ComPtr<ID3D12PipelineState> pipeline;ok(d->CreateComputePipelineState(&pd,IID_PPV_ARGS(&pipeline)));
 constexpr unsigned resultBytes=16*4*4;
 auto output=buffer(resultBytes,D3D12_HEAP_TYPE_DEFAULT,D3D12_RESOURCE_STATE_UNORDERED_ACCESS,D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS);
 auto readback=buffer(resultBytes*3,D3D12_HEAP_TYPE_READBACK,D3D12_RESOURCE_STATE_COPY_DEST);
 cmd->SetComputeRootSignature(signature.Get());cmd->SetPipelineState(pipeline.Get());ID3D12DescriptorHeap* heaps[]={heap.Get()};cmd->SetDescriptorHeaps(1,heaps);cmd->SetComputeRootDescriptorTable(1,heap->GetGPUDescriptorHandleForHeapStart());cmd->SetComputeRootUnorderedAccessView(2,output->GetGPUVirtualAddress());
 for(unsigned phase=0;phase<3;++phase){Params p{};p.alpha=phase*.5f;p.receiverCount=static_cast<unsigned>(vertices.size());cmd->SetComputeRoot32BitConstants(0,28,&p,0);cmd->Dispatch(16,1,1);barrier(output.Get(),D3D12_RESOURCE_STATE_UNORDERED_ACCESS,D3D12_RESOURCE_STATE_COPY_SOURCE);cmd->CopyBufferRegion(readback.Get(),phase*resultBytes,output.Get(),0,resultBytes);if(phase!=2)barrier(output.Get(),D3D12_RESOURCE_STATE_COPY_SOURCE,D3D12_RESOURCE_STATE_UNORDERED_ACCESS);}
 ok(cmd->Close());ID3D12CommandList* lists[]={cmd.Get()};queue->ExecuteCommandLists(1,lists);
 ComPtr<ID3D12Fence> fence;ok(d->CreateFence(0,D3D12_FENCE_FLAG_NONE,IID_PPV_ARGS(&fence)));HANDLE event=CreateEventW(nullptr,FALSE,FALSE,nullptr);ok(queue->Signal(fence.Get(),1));ok(fence->SetEventOnCompletion(1,event));if(WaitForSingleObject(event,30000)!=WAIT_OBJECT_0)throw std::runtime_error("GPU timeout");CloseHandle(event);
 D3D12_RANGE read{0,resultBytes*3};ok(readback->Map(0,&read,&mapped));const float* data=static_cast<const float*>(mapped);
 const float expected[16][4]={{1e9,0,0,0},{4.00025f,.25f,0,0},{5.25f,.25f,0,0},{8,0,0,0},{4.2222222f,.22222222f,0,0},{1e9,0,0,0},{0,0,0,0},{1,0,0,0},{0,0,0,0},{.75f,0,0,0},{.5f,0,0,0},{.25f,0,0,0},{7.5f,.75f,0,0},{0,0,0,0},{8,0,0,0},{1e9,0,0,0}};
 unsigned failed=0;
 for(unsigned phase=0;phase<3;++phase)for(unsigned c=0;c<16;++c)for(unsigned k=0;k<4;++k){float actual=data[phase*64+c*4+k];if(!std::isfinite(actual)||std::abs(actual-expected[c][k])>1e-4f){std::printf("FAIL phase=%u case=%u component=%u expected=%g actual=%g\n",phase,c,k,expected[c][k],actual);++failed;}}
 readback->Unmap(0,&empty);std::printf("48 production-shader cases on D3D12 WARP; failed components=%u\n",failed);return failed?1:0;
 }catch(const std::exception& e){std::fprintf(stderr,"%s\n",e.what());return 2;}
}
