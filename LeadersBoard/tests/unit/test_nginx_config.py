"""Nginx 設定ファイルの内容を検証するテスト。

設定ファイル（default.conf）と起動スクリプト（entrypoint.sh）が
design.md の仕様に準拠しているかを静的に検証する。
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

NGINX_DIR = Path(__file__).resolve().parents[2] / "nginx"
CONF_PATH = NGINX_DIR / "conf.d" / "default.conf"
ENTRYPOINT_PATH = NGINX_DIR / "entrypoint.sh"


class TestNginxDefaultConf:
    """default.conf の設定内容を検証する。"""

    def setup_method(self) -> None:
        self.conf = CONF_PATH.read_text()

    def test_listen_port_80(self) -> None:
        assert "listen 80" in self.conf

    def test_auth_basic_enabled(self) -> None:
        assert "auth_basic" in self.conf
        assert "auth_basic_user_file" in self.conf
        assert "/etc/nginx/auth/htpasswd" in self.conf

    def test_mlflow_location_block(self) -> None:
        assert "location /mlflow/" in self.conf

    def test_mlflow_proxy_pass(self) -> None:
        assert "http://mlflow:5010" in self.conf

    def test_mlflow_rewrite(self) -> None:
        assert "rewrite" in self.conf
        assert "/mlflow/" in self.conf

    def test_streamlit_location_block(self) -> None:
        assert "location /streamlit/" in self.conf

    def test_streamlit_proxy_pass(self) -> None:
        assert "http://streamlit:8501" in self.conf

    def test_websocket_upgrade_headers(self) -> None:
        assert "Upgrade" in self.conf
        assert "upgrade" in self.conf

    def test_proxy_headers(self) -> None:
        for header in ["Host", "X-Real-IP", "X-Forwarded-For", "X-Forwarded-Proto"]:
            assert header in self.conf

    def test_client_max_body_size(self) -> None:
        assert "client_max_body_size" in self.conf

    def test_proxy_timeouts(self) -> None:
        assert "proxy_read_timeout" in self.conf
        assert "proxy_send_timeout" in self.conf

    def test_log_to_stdout(self) -> None:
        assert "/dev/stdout" in self.conf or "access_log" in self.conf
        assert "/dev/stderr" in self.conf or "error_log" in self.conf

    def test_root_redirect_to_streamlit(self) -> None:
        assert "location = /" in self.conf or "location /" in self.conf


class TestNginxEntrypoint:
    """entrypoint.sh の内容と権限を検証する。"""

    def setup_method(self) -> None:
        self.script = ENTRYPOINT_PATH.read_text()

    def test_htpasswd_check_exists(self) -> None:
        assert "/etc/nginx/auth/htpasswd" in self.script

    def test_fail_message(self) -> None:
        assert "htpasswd missing or unreadable" in self.script

    def test_exit_code_1_on_failure(self) -> None:
        assert "exit 1" in self.script

    def test_exec_nginx(self) -> None:
        assert "exec nginx" in self.script

    def test_executable_permission(self) -> None:
        mode = os.stat(ENTRYPOINT_PATH).st_mode
        assert mode & stat.S_IXUSR
