import os
import signal
import subprocess
import threading


_process_lock = threading.Lock()
_processes = set()
_stopping = False


class ProcessCancelled(BaseException):
    pass


def start_processes():
    global _stopping
    with _process_lock:
        _stopping = False


def _kill_process_group(process):
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def stop_processes():
    global _stopping
    with _process_lock:
        _stopping = True
        for process in _processes:
            _kill_process_group(process)


def run_process(cmd, *, timeout):
    with _process_lock:
        if _stopping:
            raise ProcessCancelled()
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        _processes.add(process)
    try:
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as error:
            _kill_process_group(process)
            stdout, stderr = process.communicate()
            error.output = stdout
            error.stderr = stderr
            raise

        with _process_lock:
            if _stopping:
                raise ProcessCancelled()
        if process.returncode:
            raise subprocess.CalledProcessError(process.returncode, cmd, stdout, stderr)
        return subprocess.CompletedProcess(cmd, process.returncode, stdout, stderr)
    finally:
        with _process_lock:
            _processes.discard(process)
