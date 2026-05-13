from __future__ import annotations

import json
import subprocess
import threading
import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox, ttk


POWERSHELL_COMMAND = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command"]


def parse_ports(text: str) -> list[int]:
    normalized = text.replace("，", ",").replace("；", ",").replace("\r", ",").replace("\n", ",").replace("\t", ",")
    tokens = normalized.replace(" ", ",").split(",")
    ports: list[int] = []
    for token in tokens:
        value = token.strip()
        if not value:
            continue
        port = int(value)
        if port < 1 or port > 65535:
            raise ValueError(f"端口超出范围: {port}")
        if port not in ports:
            ports.append(port)
    if not ports:
        raise ValueError("请输入至少一个端口。")
    return ports


def run_powershell_json(script: str, timeout_seconds: int = 20) -> list[dict[str, object]]:
    completed = subprocess.run(
        [*POWERSHELL_COMMAND, script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=timeout_seconds,
    )
    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()
    if completed.returncode != 0 and not stdout:
        raise RuntimeError(stderr or "PowerShell 执行失败。")
    if not stdout:
        return []
    data = json.loads(stdout)
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        return [data]
    return []


def query_port_processes(ports: list[int]) -> list[dict[str, object]]:
    port_list = ",".join(str(port) for port in ports)
    script = f"""
$ports = @({port_list})
$connections = @(Get-NetTCPConnection -LocalPort $ports -ErrorAction SilentlyContinue |
  Sort-Object LocalPort, OwningProcess, State, RemoteAddress, RemotePort -Unique)

$result = @()
if ($connections.Count -gt 0) {{
  $pids = @($connections | Select-Object -ExpandProperty OwningProcess -Unique)
  $processesByPid = @{{}}
  if ($pids.Count -gt 0) {{
    $filter = ($pids | ForEach-Object {{ "ProcessId = $_" }}) -join " OR "
    @(Get-CimInstance Win32_Process -Filter $filter -ErrorAction SilentlyContinue) | ForEach-Object {{
      $processesByPid[[int]$_.ProcessId] = $_
    }}
  }}

  $result = foreach ($conn in $connections) {{
    $proc = $processesByPid[[int]$conn.OwningProcess]
    [PSCustomObject]@{{
      local_address = [string]$conn.LocalAddress
      local_port = [int]$conn.LocalPort
      remote_address = [string]$conn.RemoteAddress
      remote_port = [int]$conn.RemotePort
      state = [string]$conn.State
      pid = [int]$conn.OwningProcess
      process_name = if ($proc) {{ [string]$proc.Name }} else {{ "" }}
      command_line = if ($proc) {{ [string]$proc.CommandLine }} else {{ "" }}
      creation_date = if ($proc) {{ [string]$proc.CreationDate }} else {{ "" }}
    }}
  }}
}}

$result | ConvertTo-Json -Depth 4 -Compress
"""
    rows = run_powershell_json(script)
    rows.sort(key=lambda item: (int(item.get("local_port") or 0), int(item.get("pid") or 0), str(item.get("state") or "")))
    return rows


def kill_process_tree(pid: int) -> str:
    completed = subprocess.run(
        ["taskkill", "/PID", str(pid), "/T", "/F"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=20,
    )
    output = (completed.stdout or completed.stderr or "").strip()
    if completed.returncode != 0:
        raise RuntimeError(output or f"结束 PID {pid} 失败。")
    return output or f"已结束 PID {pid}"


@dataclass
class PortRow:
    local_port: int
    pid: int
    state: str
    process_name: str
    command_line: str
    local_address: str
    remote_address: str
    remote_port: int
    creation_date: str

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "PortRow":
        return cls(
            local_port=int(data.get("local_port") or 0),
            pid=int(data.get("pid") or 0),
            state=str(data.get("state") or ""),
            process_name=str(data.get("process_name") or ""),
            command_line=str(data.get("command_line") or ""),
            local_address=str(data.get("local_address") or ""),
            remote_address=str(data.get("remote_address") or ""),
            remote_port=int(data.get("remote_port") or 0),
            creation_date=str(data.get("creation_date") or ""),
        )


class PortToolApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("端口进程管理器")
        self.root.geometry("1380x820")

        self.rows: list[PortRow] = []
        self.last_ports: list[int] = [8765]
        self.busy = False

        self.port_var = tk.StringVar(value="8765")
        self.status_var = tk.StringVar(value="输入端口后点击查询。支持逗号、空格或换行分隔多个端口。")

        self._buttons: list[ttk.Button] = []

        self._build_ui()
        self.root.after(100, self.refresh_rows)

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)
        self.root.rowconfigure(2, weight=1)

        toolbar = ttk.Frame(self.root, padding=12)
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.columnconfigure(1, weight=1)

        ttk.Label(toolbar, text="端口").grid(row=0, column=0, padx=(0, 8), sticky="w")
        self.port_entry = ttk.Entry(toolbar, textvariable=self.port_var)
        self.port_entry.grid(row=0, column=1, sticky="ew")

        self.query_button = ttk.Button(toolbar, text="查询端口", command=self.refresh_rows)
        self.query_button.grid(row=0, column=2, padx=(8, 0))
        self.refresh_button = ttk.Button(toolbar, text="刷新当前结果", command=self.refresh_current_ports)
        self.refresh_button.grid(row=0, column=3, padx=(8, 0))
        self.kill_selected_button = ttk.Button(toolbar, text="结束选中进程", command=self.kill_selected)
        self.kill_selected_button.grid(row=0, column=4, padx=(8, 0))
        self.kill_all_button = ttk.Button(toolbar, text="结束当前端口全部进程", command=self.kill_all_current)
        self.kill_all_button.grid(row=0, column=5, padx=(8, 0))
        self._buttons.extend(
            [
                self.query_button,
                self.refresh_button,
                self.kill_selected_button,
                self.kill_all_button,
            ]
        )

        table_wrap = ttk.Frame(self.root, padding=(12, 0, 12, 0))
        table_wrap.grid(row=1, column=0, sticky="nsew")
        table_wrap.columnconfigure(0, weight=1)
        table_wrap.rowconfigure(0, weight=1)

        columns = ("local_port", "pid", "state", "process_name", "local_address", "remote_address", "remote_port")
        self.tree = ttk.Treeview(table_wrap, columns=columns, show="headings", height=16)
        headings = {
            "local_port": "本地端口",
            "pid": "PID",
            "state": "状态",
            "process_name": "进程名",
            "local_address": "本地地址",
            "remote_address": "远端地址",
            "remote_port": "远端端口",
        }
        widths = {
            "local_port": 90,
            "pid": 90,
            "state": 120,
            "process_name": 180,
            "local_address": 130,
            "remote_address": 160,
            "remote_port": 100,
        }
        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(column, width=widths[column], anchor="w")

        scroll_y = ttk.Scrollbar(table_wrap, orient="vertical", command=self.tree.yview)
        scroll_x = ttk.Scrollbar(table_wrap, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        detail_wrap = ttk.Frame(self.root, padding=12)
        detail_wrap.grid(row=2, column=0, sticky="nsew")
        detail_wrap.columnconfigure(0, weight=1)
        detail_wrap.rowconfigure(1, weight=1)

        ttk.Label(detail_wrap, text="进程详情 / 操作日志").grid(row=0, column=0, sticky="w")
        self.detail_text = tk.Text(detail_wrap, wrap="word", font=("Consolas", 10))
        self.detail_text.grid(row=1, column=0, sticky="nsew")

        status_bar = ttk.Label(self.root, textvariable=self.status_var, padding=(12, 0, 12, 12))
        status_bar.grid(row=3, column=0, sticky="ew")

    def set_busy(self, busy: bool, message: str) -> None:
        self.busy = busy
        state = "disabled" if busy else "normal"
        for button in self._buttons:
            button.configure(state=state)
        self.port_entry.configure(state=state)
        self.status_var.set(message)

    def run_background(
        self,
        work: callable,
        on_success: callable,
        success_message: str,
        error_title: str,
        busy_message: str,
    ) -> None:
        if self.busy:
            return
        self.set_busy(True, busy_message)

        def worker() -> None:
            try:
                result = work()
            except Exception as exc:
                self.root.after(0, lambda: self._finish_with_error(error_title, exc))
                return
            self.root.after(0, lambda: self._finish_with_success(on_success, result, success_message))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_with_error(self, error_title: str, exc: Exception) -> None:
        self.set_busy(False, f"{error_title}: {exc}")
        messagebox.showerror(error_title, str(exc))

    def _finish_with_success(self, on_success: callable, result: object, success_message: str) -> None:
        on_success(result)
        self.set_busy(False, success_message)

    def refresh_current_ports(self) -> None:
        self.port_var.set(", ".join(str(port) for port in self.last_ports))
        self.refresh_rows()

    def refresh_rows(self) -> None:
        try:
            ports = parse_ports(self.port_var.get())
        except Exception as exc:
            messagebox.showerror("端口错误", str(exc))
            return

        self.last_ports = ports
        port_text = ", ".join(str(port) for port in ports)
        self.run_background(
            work=lambda: (ports, query_port_processes(ports)),
            on_success=self._apply_refreshed_rows,
            success_message=f"查询完成: {port_text}",
            error_title="查询失败",
            busy_message=f"正在查询端口: {port_text}",
        )

    def _apply_refreshed_rows(self, payload: object) -> None:
        ports, raw_rows = payload
        self.rows = [PortRow.from_dict(item) for item in raw_rows]

        for item_id in self.tree.get_children():
            self.tree.delete(item_id)

        for index, row in enumerate(self.rows):
            self.tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    row.local_port,
                    row.pid,
                    row.state,
                    row.process_name,
                    row.local_address,
                    row.remote_address,
                    row.remote_port,
                ),
            )

        self.detail_text.delete("1.0", "end")
        if not self.rows:
            self.detail_text.insert("1.0", "当前端口没有发现正在运行的监听或连接进程。")
            self.status_var.set(f"查询完成: {', '.join(str(port) for port in ports)}，未发现进程。")
            return

        self.status_var.set(f"查询完成: {', '.join(str(port) for port in ports)}，共发现 {len(self.rows)} 条连接记录。")
        self.tree.selection_set("0")
        self.on_select()

    def on_select(self, event: object | None = None) -> None:
        selected = self.tree.selection()
        self.detail_text.delete("1.0", "end")
        if not selected:
            self.detail_text.insert("1.0", "请选择一条记录。")
            return

        lines: list[str] = []
        for item_id in selected:
            row = self.rows[int(item_id)]
            lines.extend(
                [
                    f"端口: {row.local_port}",
                    f"PID: {row.pid}",
                    f"进程名: {row.process_name or '-'}",
                    f"状态: {row.state or '-'}",
                    f"本地地址: {row.local_address or '-'}",
                    f"远端地址: {row.remote_address or '-'}:{row.remote_port}",
                    f"创建时间: {row.creation_date or '-'}",
                    "命令行:",
                    row.command_line or "-",
                    "",
                    "-" * 72,
                    "",
                ]
            )
        self.detail_text.insert("1.0", "\n".join(lines).strip())

    def kill_selected(self) -> None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("提示", "请先选中至少一条记录。")
            return
        pids = sorted({self.rows[int(item_id)].pid for item_id in selected})
        self._start_kill(pids, "结束选中进程")

    def kill_all_current(self) -> None:
        if not self.rows:
            messagebox.showinfo("提示", "当前没有可结束的进程。")
            return
        pids = sorted({row.pid for row in self.rows})
        self._start_kill(pids, "结束当前端口全部进程")

    def _start_kill(self, pids: list[int], title: str) -> None:
        if not pids:
            messagebox.showinfo("提示", "没有找到可结束的 PID。")
            return
        message = "将要结束以下 PID：\n" + ", ".join(str(pid) for pid in pids)
        if not messagebox.askyesno(title, message):
            return

        self.run_background(
            work=lambda: self._kill_pids(pids),
            on_success=self._apply_kill_results,
            success_message=f"{title} 完成",
            error_title=title,
            busy_message=f"{title} 中...",
        )

    def _kill_pids(self, pids: list[int]) -> list[str]:
        logs: list[str] = []
        for pid in pids:
            try:
                result = kill_process_tree(pid)
                logs.append(f"[done] PID {pid}: {result}")
            except Exception as exc:
                logs.append(f"[failed] PID {pid}: {exc}")
        return logs

    def _apply_kill_results(self, logs: object) -> None:
        messages = [str(item) for item in logs]
        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("1.0", "\n".join(messages))
        self.root.after(150, self.refresh_current_ports)


def main() -> None:
    root = tk.Tk()
    app = PortToolApp(root)
    app.port_entry.focus_set()
    root.mainloop()


if __name__ == "__main__":
    main()
