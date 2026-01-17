import os
import sys
import time
import threading
import webbrowser
import socket
import tempfile
import traceback
from pathlib import Path


def _log_path() -> str:
    return os.path.join(tempfile.gettempdir(), "cvbuilderats_desktop_linux.log")


def log(msg: str) -> None:
    try:
        with open(_log_path(), "a", encoding="utf-8") as f:
            f.write(msg.rstrip() + "\n")
    except Exception:
        pass


def resource_path(rel_path: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base, rel_path)


def _find_free_port(preferred: int = 8501) -> int:
    def is_free(p: int) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", p), timeout=0.2):
                return False
        except Exception:
            return True

    if is_free(preferred):
        return preferred

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _single_instance_or_exit() -> None:
    lock_path = os.path.join(tempfile.gettempdir(), "cvbuilderats_single_instance.lock")
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
        log(f"single-instance lock acquired: {lock_path}")
    except FileExistsError:
        log("single-instance lock exists; exiting.")
        raise SystemExit(0)


def _wait_for_port(port: int, timeout_s: float = 20.0) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                return True
        except Exception:
            time.sleep(0.25)
    return False


def _open_browser_when_ready(url: str, port: int) -> None:
    if _wait_for_port(port, timeout_s=25.0):
        try:
            webbrowser.open(url)
            log(f"Opened browser: {url}")
        except Exception as e:
            log(f"webbrowser.open failed: {e!r}")
    else:
        log(f"Server did not respond on port {port} in time. Open manually: {url}")


def _write_streamlit_config(tmp_dir: str) -> str:
    cfg_dir = Path(tmp_dir) / "streamlit_cfg"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = cfg_dir / "config.toml"

    cfg_path.write_text(
        "\n".join([
            "[global]",
            "developmentMode = false",
            "",
            "[browser]",
            "gatherUsageStats = false",
            "",
            "[server]",
            "headless = true",
            "enableCORS = false",
            "enableXsrfProtection = false",
            "runOnSave = false",
            'fileWatcherType = "none"',
            "",
        ]),
        encoding="utf-8",
    )
    return str(cfg_dir)


def main():
    with open(_log_path(), "w", encoding="utf-8") as f:
        f.write("CVBuilderATS Linux launcher starting...\n")

    try:
        _single_instance_or_exit()

        app_path = resource_path("app.py")
        preferred = int(os.environ.get("CVBUILDER_PORT", "8501"))
        port = _find_free_port(preferred)
        url = f"http://localhost:{port}"

        log(f"app_path={app_path}")
        log(f"port={port} url={url}")

        # Force non-dev + private config (ignore user's ~/.streamlit)
        os.environ["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"
        os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
        os.environ["STREAMLIT_SERVER_HEADLESS"] = "true"

        tmp_dir = tempfile.mkdtemp(prefix="cvbuilderats_")
        cfg_dir = _write_streamlit_config(tmp_dir)
        os.environ["STREAMLIT_CONFIG_DIR"] = cfg_dir
        log(f"STREAMLIT_CONFIG_DIR={cfg_dir}")

        # Open browser only when ready
        threading.Thread(target=_open_browser_when_ready, args=(url, port), daemon=True).start()

        from streamlit.web import cli as stcli

        sys.argv = [
            "streamlit",
            "run",
            app_path,
            "--server.address", "127.0.0.1",
            "--server.port", str(port),
            "--server.headless", "true",
            "--browser.gatherUsageStats", "false",
            "--server.runOnSave", "false",
            "--server.fileWatcherType", "none",
        ]

        log("Starting Streamlit...")
        stcli.main()

    except SystemExit:
        pass
    except Exception:
        tb = traceback.format_exc()
        log("FATAL ERROR:\n" + tb)
        try:
            sys.stderr.write(tb + "\n")
        except Exception:
            pass


if __name__ == "__main__":
    main()
