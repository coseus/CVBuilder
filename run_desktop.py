#for Windows
import os
import sys
import time
import threading
import webbrowser
import socket
import tempfile
from pathlib import Path


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


def _open_browser_once(url: str, delay: float = 1.2) -> None:
    time.sleep(delay)
    lock_path = os.path.join(tempfile.gettempdir(), "cvbuilderats_browser_open.lock")
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(url)
    except FileExistsError:
        return
    except Exception:
        return

    try:
        webbrowser.open(url)
    except Exception:
        pass


def _write_streamlit_config(tmp_dir: str) -> str:
    """
    Create a local Streamlit config that forces non-dev mode and stable desktop settings.
    This prevents conflicts with user's global ~/.streamlit/config.toml.
    """
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
        encoding="utf-8"
    )
    return str(cfg_dir)


def main():
    app_path = resource_path("app.py")

    preferred = int(os.environ.get("CVBUILDER_PORT", "8501"))
    port = _find_free_port(preferred)
    url = f"http://localhost:{port}"

    # --- HARD FORCE: disable dev mode regardless of user's global config ---
    os.environ["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"
    os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    os.environ["STREAMLIT_SERVER_HEADLESS"] = "true"

    # Use a private config dir (ignores user's %USERPROFILE%\.streamlit\config.toml)
    tmp_dir = tempfile.mkdtemp(prefix="cvbuilderats_")
    cfg_dir = _write_streamlit_config(tmp_dir)
    os.environ["STREAMLIT_CONFIG_DIR"] = cfg_dir

    # Open browser once
    threading.Thread(target=_open_browser_once, args=(url, 1.2), daemon=True).start()

    # Start Streamlit programmatically
    from streamlit.web import cli as stcli

    # We keep --server.port (now allowed because dev mode forced off)
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

    stcli.main()


if __name__ == "__main__":
    main()
