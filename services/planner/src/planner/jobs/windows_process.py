"""Windows 10+ atomic job assignment; no execution-before-containment window.

CreateProcessW receives PROC_THREAD_ATTRIBUTE_JOB_LIST, so even a fast redirector
is born in our non-inheritable kill-on-close job. Handle inheritance is restricted
to a single NUL handle. Unsupported job containment fails before launching work.
"""

import ctypes as c
import os
import subprocess
import time
from ctypes import wintypes as w


class BasicLimits(c.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", c.c_longlong),
        ("PerJobUserTimeLimit", c.c_longlong),
        ("LimitFlags", w.DWORD),
        ("MinimumWorkingSetSize", c.c_size_t),
        ("MaximumWorkingSetSize", c.c_size_t),
        ("ActiveProcessLimit", w.DWORD),
        ("Affinity", c.c_size_t),
        ("PriorityClass", w.DWORD),
        ("SchedulingClass", w.DWORD),
    ]


class IoCounters(c.Structure):
    _fields_ = [
        (name, c.c_ulonglong)
        for name in (
            "ReadOperationCount",
            "WriteOperationCount",
            "OtherOperationCount",
            "ReadTransferCount",
            "WriteTransferCount",
            "OtherTransferCount",
        )
    ]


class ExtendedLimits(c.Structure):
    _fields_ = [
        ("BasicLimitInformation", BasicLimits),
        ("IoInfo", IoCounters),
        ("ProcessMemoryLimit", c.c_size_t),
        ("JobMemoryLimit", c.c_size_t),
        ("PeakProcessMemoryUsed", c.c_size_t),
        ("PeakJobMemoryUsed", c.c_size_t),
    ]


class Accounting(c.Structure):
    _fields_ = [
        ("TotalUserTime", c.c_longlong),
        ("TotalKernelTime", c.c_longlong),
        ("ThisPeriodTotalUserTime", c.c_longlong),
        ("ThisPeriodTotalKernelTime", c.c_longlong),
        ("TotalPageFaultCount", w.DWORD),
        ("TotalProcesses", w.DWORD),
        ("ActiveProcesses", w.DWORD),
        ("TotalTerminatedProcesses", w.DWORD),
    ]


class StartupInfo(c.Structure):
    _fields_ = [
        ("cb", w.DWORD),
        ("lpReserved", w.LPWSTR),
        ("lpDesktop", w.LPWSTR),
        ("lpTitle", w.LPWSTR),
        ("dwX", w.DWORD),
        ("dwY", w.DWORD),
        ("dwXSize", w.DWORD),
        ("dwYSize", w.DWORD),
        ("dwXCountChars", w.DWORD),
        ("dwYCountChars", w.DWORD),
        ("dwFillAttribute", w.DWORD),
        ("dwFlags", w.DWORD),
        ("wShowWindow", w.WORD),
        ("cbReserved2", w.WORD),
        ("lpReserved2", c.c_void_p),
        ("hStdInput", w.HANDLE),
        ("hStdOutput", w.HANDLE),
        ("hStdError", w.HANDLE),
    ]


class StartupInfoEx(c.Structure):
    _fields_ = [("StartupInfo", StartupInfo), ("lpAttributeList", c.c_void_p)]


class ProcessInfo(c.Structure):
    _fields_ = [
        ("hProcess", w.HANDLE),
        ("hThread", w.HANDLE),
        ("dwProcessId", w.DWORD),
        ("dwThreadId", w.DWORD),
    ]


class SecurityAttributes(c.Structure):
    _fields_ = [
        ("nLength", w.DWORD),
        ("lpSecurityDescriptor", c.c_void_p),
        ("bInheritHandle", w.BOOL),
    ]


def _api(name, result, *args):
    function = getattr(c.WinDLL("kernel32", use_last_error=True), name)
    function.restype, function.argtypes = result, args
    return function


CreateJob = _api("CreateJobObjectW", w.HANDLE, c.c_void_p, w.LPCWSTR)
SetJob = _api("SetInformationJobObject", w.BOOL, w.HANDLE, c.c_int, c.c_void_p, w.DWORD)
QueryJob = _api(
    "QueryInformationJobObject", w.BOOL, w.HANDLE, c.c_int, c.c_void_p, w.DWORD, c.c_void_p
)
TerminateJob = _api("TerminateJobObject", w.BOOL, w.HANDLE, w.UINT)
CloseHandle = _api("CloseHandle", w.BOOL, w.HANDLE)
CreateFile = _api(
    "CreateFileW", w.HANDLE, w.LPCWSTR, w.DWORD, w.DWORD, c.c_void_p, w.DWORD, w.DWORD, w.HANDLE
)
InitializeAttributes = _api(
    "InitializeProcThreadAttributeList", w.BOOL, c.c_void_p, w.DWORD, w.DWORD, c.POINTER(c.c_size_t)
)
UpdateAttributes = _api(
    "UpdateProcThreadAttribute",
    w.BOOL,
    c.c_void_p,
    w.DWORD,
    c.c_size_t,
    c.c_void_p,
    c.c_size_t,
    c.c_void_p,
    c.c_void_p,
)
DeleteAttributes = _api("DeleteProcThreadAttributeList", None, c.c_void_p)
CreateProcess = _api(
    "CreateProcessW",
    w.BOOL,
    w.LPCWSTR,
    w.LPWSTR,
    c.c_void_p,
    c.c_void_p,
    w.BOOL,
    w.DWORD,
    c.c_void_p,
    w.LPCWSTR,
    c.c_void_p,
    c.POINTER(ProcessInfo),
)
Wait = _api("WaitForSingleObject", w.DWORD, w.HANDLE, w.DWORD)
ExitCode = _api("GetExitCodeProcess", w.BOOL, w.HANDLE, c.POINTER(w.DWORD))


def checked(result):
    if not result:
        raise c.WinError(c.get_last_error())
    return result


class WindowsProcessTree:
    def __init__(self, command, *, env=None, cwd=None):
        self.command, self.returncode = command, None
        self.job, self.handle = None, None
        attributes, null, info = None, None, ProcessInfo()
        try:
            self.job = checked(CreateJob(None, None))
            limits = ExtendedLimits()
            limits.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE
            checked(SetJob(self.job, 9, c.byref(limits), c.sizeof(limits)))
            security = SecurityAttributes(c.sizeof(SecurityAttributes), None, True)
            null = CreateFile("NUL", 0xC0000000, 3, c.byref(security), 3, 0, None)
            if null == c.c_void_p(-1).value:
                null = None
                raise c.WinError(c.get_last_error())
            size = c.c_size_t()
            InitializeAttributes(None, 2, 0, c.byref(size))
            storage = c.create_string_buffer(size.value)
            checked(InitializeAttributes(storage, 2, 0, c.byref(size)))
            attributes = storage
            jobs, handles = (w.HANDLE * 1)(self.job), (w.HANDLE * 1)(null)
            checked(UpdateAttributes(attributes, 0, 0x2000D, jobs, c.sizeof(jobs), None, None))
            checked(
                UpdateAttributes(attributes, 0, 0x20002, handles, c.sizeof(handles), None, None)
            )
            startup = StartupInfoEx()
            startup.StartupInfo.cb = c.sizeof(startup)
            startup.StartupInfo.dwFlags = 0x100  # STARTF_USESTDHANDLES
            startup.StartupInfo.hStdInput = null
            startup.StartupInfo.hStdOutput = null
            startup.StartupInfo.hStdError = null
            startup.lpAttributeList = c.cast(attributes, c.c_void_p)
            environment = None
            if env is not None:
                if any("\0" in key or "=" in key or "\0" in value for key, value in env.items()):
                    raise ValueError("Invalid environment key or value")
                environment = c.create_unicode_buffer(
                    "\0".join(
                        f"{key}={value}"
                        for key, value in sorted(env.items(), key=lambda pair: pair[0].upper())
                    )
                    + "\0"
                )
            checked(
                CreateProcess(
                    None,
                    c.create_unicode_buffer(subprocess.list2cmdline(command)),
                    None,
                    None,
                    True,
                    0x08000000 | 0x00080000 | 0x00000400,  # NO_WINDOW | EXTENDED | UNICODE
                    environment,
                    os.fspath(cwd) if cwd is not None else None,
                    c.byref(startup),
                    c.byref(info),
                )
            )
            self.handle, self.pid = info.hProcess, info.dwProcessId
        except BaseException:
            if self.job:
                CloseHandle(self.job)
                self.job = None
            if info.hProcess:
                CloseHandle(info.hProcess)
            raise
        finally:
            if info.hThread:
                CloseHandle(info.hThread)
            if attributes is not None:
                DeleteAttributes(attributes)
            if null:
                CloseHandle(null)

    def poll(self):
        if self.returncode is None:
            state = Wait(self.handle, 0)
            if state == 0xFFFFFFFF:
                raise c.WinError(c.get_last_error())
            if state == 0:
                code = w.DWORD()
                checked(ExitCode(self.handle, c.byref(code)))
                self.returncode = code.value
        return self.returncode

    def wait(self, timeout):
        state = Wait(self.handle, max(0, int(timeout * 1000)))
        if state == 0x102:
            raise subprocess.TimeoutExpired(self.command, timeout)
        if state == 0xFFFFFFFF:
            raise c.WinError(c.get_last_error())
        return self.poll()

    def kill(self):
        checked(TerminateJob(self.job, 1))

    def close(self):
        try:
            self.kill()
            self.wait(timeout=1)
            # Termination is asynchronous. Do not report cleanup while descendants run.
            deadline = time.monotonic() + 1
            accounting = Accounting()
            while True:
                checked(QueryJob(self.job, 1, c.byref(accounting), c.sizeof(accounting), None))
                if not accounting.ActiveProcesses:
                    break
                if time.monotonic() >= deadline:
                    raise subprocess.TimeoutExpired(self.command, 1)
                time.sleep(0.005)
        finally:
            CloseHandle(self.handle)
            CloseHandle(self.job)
            self.handle = self.job = None
