"""Own a trusted worker's descendants, including Windows venv redirectors."""

import os
import signal
import subprocess


class PosixProcessTree:
    def __init__(self, command, *, env=None, cwd=None):
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            env=env,
            cwd=cwd,
        )

    @property
    def returncode(self):
        return self.process.returncode

    def poll(self):
        return self.process.poll()

    def wait(self, timeout):
        return self.process.wait(timeout=timeout)

    def kill(self):
        # Also clean descendants when the original process has already exited.
        try:
            os.killpg(self.process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    def close(self):
        self.kill()
        self.process.wait(timeout=1)


def spawn_process_tree(command, *, env=None, cwd=None):
    if os.name == "nt":
        from planner.jobs.windows_process import WindowsProcessTree

        return WindowsProcessTree(command, env=env, cwd=cwd)
    return PosixProcessTree(command, env=env, cwd=cwd)
