# Process-tree deadline and cancellation recovery

2026-09-25. Production `run_process` previously terminated only its direct `Popen` child. A Windows virtual-environment Python can be a redirector that starts another interpreter. A normal helper can also start descendants on either platform. Returning from the wrapper did not prove those descendants had stopped.

## Reproduction and correction

`tests/fault/test_process_tree.py` starts a real interpreter which launches another interpreter. The descendant writes a ready marker, then would write a late marker one second later. The pre-fix run failed all four cleanup cases: timeout, superseded cancellation, normal parent exit and a failing state callback. The environment/cwd API regression also failed before implementation. Raw result: [five red failures](raw/process-tree-red.txt).

Windows now creates each process with an atomic `PROC_THREAD_ATTRIBUTE_JOB_LIST` attribute referring to a new Job Object. This avoids both a running-child race and a suspended-but-not-yet-assigned crash gap. The Job Object has kill-on-close enabled and is not inherited; only an explicit NUL standard-stream handle is inherited. A containment failure prevents execution. Completion/cancellation kills the job, waits for the direct process, then verifies the job has no active descendants before releasing handles. A hard supervisor exit also closes the job in the kernel.

This uses the documented [job-list creation attribute](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute) and [Job Object lifetime rules](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects). Windows 10 / Server 2016 or newer is required; unsupported containment fails closed. The [termination API](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-terminatejobobject) terminates associated nested jobs as well.

POSIX children start in a new session. Every exit path sends SIGKILL to that owned process group, including when the immediate parent exited naturally. This uses Python's documented [start_new_session behavior](https://docs.python.org/3/library/subprocess.html). The independent watchdog enforces the owned scope's deadline even while a state callback is blocked; it is joined before handles are closed. A further [red regression](raw/process-tree-parent-exit-red.txt) proved that checking only parent liveness in the watchdog could miss a surviving descendant after parent exit. The watchdog now kills the scope unconditionally at its deadline. The wrapper can take longer to return when its callback blocks, but the child work is stopped by the watchdog.

## Executed verification

- Windows: `.venv/Scripts/python.exe -m pytest tests/fault/test_process_tree.py tests/fault/test_job_recovery.py -q`: **18 passed in 13.40s**, including actual solver result/fallback and worker lease shutdown. [Raw result](raw/process-tree-green.txt).
- Linux: actual `adaptive-planner:local-r4` image, production dependencies and current source mounted read-only, network disabled. Pytest's pure-Python dependencies were appended from the local locked environment; no provider or package download occurred. The same process-tree suite produced **7 passed, 2 Windows-only skipped in 8.18s**. [Raw result](raw/process-tree-linux.txt).
- Ruff format/check passed for the changed production and test files.

The Linux replay command mounts `services/planner/src` at `/app/services/planner/src`, the local `.venv/Lib/site-packages` at `/windows-deps`, and the single test file at `/review/test_process_tree.py`, using `--rm --network none` and `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`. Its Python command is `import sys; sys.path.append('/windows-deps'); import pytest; raise SystemExit(pytest.main(['/review/test_process_tree.py', '-q', '--confcutdir=/review', '-p', 'no:cacheprovider']))`. Production packages resolve from the image before that appended path.

Independent backend review found no actionable Win32 layout/lifecycle defect and reproduced the original issue through its own benchmark descendant-marker case; adopting the utility made that regression pass. The final watchdog edge was also sent to that reviewer before a new benchmark manifest is frozen.

## Scope and limits

`run_process(command, *, timeout_seconds=5, is_cancelled=None, on_heartbeat=None, env=None, cwd=None)` retains its `ProcessResult` return contract. Output is discarded as before; callers write structured result artifacts themselves. Frozen benchmark v2 code/results were not changed; future benchmark runners may adopt this utility with a new manifest.

This lifecycle wrapper runs trusted planner workers. POSIX process groups are not a security sandbox: deliberately daemonizing into another session is outside this mechanism, and abrupt supervisor death requires container/process-manager cleanup. Windows crash cleanup is exercised directly. No unrelated processes are enumerated or terminated.
