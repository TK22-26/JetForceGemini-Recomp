"""ROM-free storage migration/restart check on an isolated Windows desktop.
Requires the JFG_STORAGE_TEST frontend target. Never launches the game.
"""
from pathlib import Path
import argparse, ctypes as c, ctypes.wintypes as w, hashlib, json, os, shutil, time

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("launcher",type=Path)
    parser.add_argument("evidence",type=Path)
    args=parser.parse_args()
    assert args.launcher.name=="JFG-Launcher-StorageTests.exe"
    assert "JFG_TEST_STORAGE_ROOT".encode("utf-16-le") in args.launcher.read_bytes()
    root=args.evidence.resolve()
    root.mkdir(parents=True,exist_ok=False)
    package=root/"package";package.mkdir()
    exe=package/"JFG-Launcher.exe";shutil.copy2(args.launcher,exe)
    names=["jfg-native-boot.exe","SDL2.dll","dxcompiler.dll","dxil.dll","concrt140.dll","msvcp140.dll","msvcp140_1.dll","msvcp140_2.dll","msvcp140_atomic_wait.dll","msvcp140_codecvt_ids.dll","vccorlib140.dll","vcruntime140.dll","vcruntime140_1.dll","vcruntime140_threads.dll"]
    pe=bytearray(128);pe[:2]=b"MZ";pe[60]=80;pe[80:82]=b"PE";pe[84:86]=b"\x64\x86"
    files=[]
    for name in names:
        data=bytes(pe) # Package validation checks PE architecture for bundled DLLs too.
        (package/name).write_bytes(data)
        files.append({"name":name,"size":len(data),"sha256":hashlib.sha256(data).hexdigest()})
    (package/"jfg-package.json").write_text(json.dumps({"schema":1,"version":"fixture","files":files}))
    original=root/"local"/"JFGRecomp"/"profiles"/"default"
    original.mkdir(parents=True);(original/"jfg.flash").write_bytes(b"original-save")
    portable=package/"userdata"/"profiles"/"default"
    portable.parent.parent.mkdir()
    user=c.WinDLL("user32",use_last_error=True);kernel=c.WinDLL("kernel32",use_last_error=True)
    user.CreateDesktopW.argtypes=[w.LPCWSTR,w.LPCWSTR,c.c_void_p,w.DWORD,w.DWORD,c.c_void_p];user.CreateDesktopW.restype=w.HANDLE
    user.CloseDesktop.argtypes=[w.HANDLE]
    enum=c.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM)
    user.EnumDesktopWindows.argtypes=[w.HANDLE,enum,w.LPARAM]
    user.GetClassNameW.argtypes=[w.HWND,w.LPWSTR,c.c_int]
    user.GetWindowTextW.argtypes=[w.HWND,w.LPWSTR,c.c_int]
    user.IsWindow.argtypes=[w.HWND];user.IsWindow.restype=w.BOOL
    user.GetWindowThreadProcessId.argtypes=[w.HWND,c.POINTER(w.DWORD)]
    user.SendMessageTimeoutW.argtypes=[w.HWND,w.UINT,w.WPARAM,w.LPARAM,w.UINT,w.UINT,c.POINTER(c.c_size_t)]
    user.SendMessageTimeoutW.restype=w.LPARAM
    user.PostMessageW.argtypes=[w.HWND,w.UINT,w.WPARAM,w.LPARAM]
    class Startup(c.Structure):
        _fields_=[("cb",w.DWORD),("lpReserved",w.LPWSTR),("lpDesktop",w.LPWSTR),("lpTitle",w.LPWSTR),
          ("dwX",w.DWORD),("dwY",w.DWORD),("dwXSize",w.DWORD),("dwYSize",w.DWORD),
          ("dwXCountChars",w.DWORD),("dwYCountChars",w.DWORD),("dwFillAttribute",w.DWORD),
          ("dwFlags",w.DWORD),("wShowWindow",w.WORD),("cbReserved2",w.WORD),("lpReserved2",c.c_void_p),
          ("hStdInput",w.HANDLE),("hStdOutput",w.HANDLE),("hStdError",w.HANDLE)]
    class Process(c.Structure):
        _fields_=[("process",w.HANDLE),("thread",w.HANDLE),("pid",w.DWORD),("tid",w.DWORD)]
    class CopyData(c.Structure):
        _fields_=[("tag",c.c_size_t),("size",w.DWORD),("data",c.c_void_p)]
    kernel.CreateProcessW.argtypes=[w.LPCWSTR,w.LPWSTR,c.c_void_p,c.c_void_p,w.BOOL,w.DWORD,c.c_void_p,w.LPCWSTR,c.POINTER(Startup),c.POINTER(Process)]
    kernel.CreateProcessW.restype=w.BOOL
    kernel.CloseHandle.argtypes=[w.HANDLE]
    desktop_name="JfgStorageSmoke-"+str(os.getpid())
    desktop=user.CreateDesktopW(desktop_name,None,None,0,0x10000000,None)
    assert desktop,c.get_last_error()
    def windows():
        result=[]
        @enum
        def visit(hwnd,_):
            cls=c.create_unicode_buffer(128);title=c.create_unicode_buffer(128);pid=w.DWORD()
            user.GetClassNameW(hwnd,cls,128);user.GetWindowTextW(hwnd,title,128);user.GetWindowThreadProcessId(hwnd,c.byref(pid))
            result.append((hwnd,cls.value,title.value,pid.value));return True
        user.EnumDesktopWindows(desktop,visit,0);return result
    def wait_for(predicate,seconds=35):
        until=time.monotonic()+seconds
        while time.monotonic()<until:
            value=predicate()
            if value:return value
            time.sleep(.05)
        raise RuntimeError("Timed out; windows="+repr(windows()))
    def frontend(exclude=0):
        return next((x for x in windows() if x[1]=="JfgFrontend" and x[3]!=exclude),None)
    def ready(profile):
        p=profile/"frontend-status.txt"
        return p.exists() and "Import your ROM once" in p.read_text(encoding="utf-8")
    def switch(host,destination,current):
        def idle():
            state=c.c_size_t()
            return user.SendMessageTimeoutW(host[0],0x8000+41,0,0,2,1000,c.byref(state)) and not(state.value&2)
        # A status file from a previous launch is not a ready-state receipt.
        # The real Game menu waits for its startup worker too.
        wait_for(lambda:idle() and ready(current))
        user.PostMessageW(host[0],0x111,117,0) # Game > Settings
        child=wait_for(lambda:next((x for x in windows() if x[1]=="JfgRmlLiveTool" and x[2]=="Settings"),None))
        dark_chrome(host[0]);dark_chrome(child[0])
        request=c.create_unicode_buffer(str(destination),32768);packet=CopyData(0x4a464753,c.sizeof(request),c.addressof(request));reply=c.c_size_t()
        assert user.SendMessageTimeoutW(host[0],0x4a,child[0],c.addressof(packet),2,15000,c.byref(reply)) and reply.value==1,"storage apply rejected"
        wait_for(lambda:not user.IsWindow(host[0]))
        return wait_for(lambda:frontend(host[3]))
    prior=os.environ.get("JFG_TEST_STORAGE_ROOT")
    os.environ["JFG_TEST_STORAGE_ROOT"]=str(root/"local")
    dwm=c.WinDLL("dwmapi")
    dwm.DwmGetWindowAttribute.argtypes=[w.HWND,w.DWORD,c.c_void_p,w.DWORD]
    dwm.DwmGetWindowAttribute.restype=c.c_long
    def dark_chrome(window):
        value=w.BOOL()
        assert dwm.DwmGetWindowAttribute(window,20,c.byref(value),c.sizeof(value))==0 and value.value,"native dark title bar missing"
    events=[]
    try:
        startup=Startup();startup.cb=c.sizeof(startup);startup.lpDesktop=desktop_name;child=Process()
        command=c.create_unicode_buffer('"'+str(exe)+'"')
        assert kernel.CreateProcessW(str(exe),command,None,None,False,0,None,str(package),c.byref(startup),c.byref(child)),c.get_last_error()
        kernel.CloseHandle(child.thread);kernel.CloseHandle(child.process)
        host=wait_for(frontend);events.append({"phase":"normal","pid":host[3]})
        host=switch(host,portable.parent.parent,original);wait_for(lambda:ready(portable))
        assert (package/"storage-location.txt").read_text().strip()=="userdata"
        assert (portable/"jfg.flash").read_bytes()==b"original-save"
        assert (original/"jfg.flash").read_bytes()==b"original-save"
        events.append({"phase":"portable","pid":host[3]})
        (portable/"jfg.flash").write_bytes(b"new-portable-progress")
        host=switch(host,original.parent.parent,portable);wait_for(lambda:ready(original))
        assert Path((package/"storage-location.txt").read_text().strip())==original.parent.parent
        assert (original/"jfg.flash").read_bytes()==b"original-save"
        assert (portable/"jfg.flash").read_bytes()==b"new-portable-progress"
        events.append({"phase":"normal-restored","pid":host[3]})
        host=switch(host,portable.parent.parent,original);wait_for(lambda:ready(portable))
        assert (portable/"jfg.flash").read_bytes()==b"new-portable-progress"
        events.append({"phase":"existing-portable-restored","pid":host[3]})
        user.PostMessageW(host[0],0x10,0,0);wait_for(lambda:not frontend())
        (root/"result.json").write_text(json.dumps({"passed":True,"events":events,"rom_or_gameplay":False},indent=2))
    finally:
        for hwnd,cls,_,_ in windows():
            if cls in ("JfgFrontend","JfgRmlLiveTool"):user.PostMessageW(hwnd,0x10,0,0)
        if prior is None:os.environ.pop("JFG_TEST_STORAGE_ROOT",None)
        else:os.environ["JFG_TEST_STORAGE_ROOT"]=prior
        user.CloseDesktop(desktop)
    print(json.dumps({"passed":True,"evidence":str(root),"restarts":3}))
if __name__=="__main__":main()
