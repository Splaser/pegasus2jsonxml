#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
简单的 jsondb Inspector（基于 Tkinter）

功能：
- 打开 jsondb/<platform>.json
- 左侧列表查看 games 列表
- 右侧：
  - 基本字段编辑（game / canonical_name / file / roms / sort_by / developer / description）
  - ROM Hashes 只读表格（rom_hashes）
  - Raw JSON 全字段只读视图
- 新增 / 删除 / 保存

注意：
- 只编辑 games 列表，不动顶层字段（schema_version / platform / collection 等）
- roms 在界面中用逗号分隔字符串表示，保存时会写回为 list[str]
"""

import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

JSONDB_DIR = Path("jsondb")


class JsonDbInspector(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("jsondb Inspector")
        self.geometry("1200x700")

        self.json_path: Path | None = None
        self.payload: dict | None = None
        self.games: list[dict] = []
        self.current_index: int | None = None
        self.dirty: bool = False
        self._suspend_dirty = False
        self._select_lock = False

        # 右侧额外视图
        self.fields: dict = {}
        self.hash_tree: ttk.Treeview | None = None
        self.raw_text: tk.Text | None = None

        self._build_ui()

    def _set_field(self, key, value):
        widget = self.fields.get(key)
        if widget is None:
            return
        if isinstance(widget, tk.StringVar):
            widget.set(value if value is not None else "")
        elif isinstance(widget, tk.Text):
            widget.delete("1.0", tk.END)
            widget.insert(tk.END, value if value is not None else "")

    # ---------------- UI 构建 ----------------
    def _build_ui(self):
        # 顶部工具栏
        toolbar = ttk.Frame(self)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        ttk.Button(toolbar, text="打开 jsondb", command=self.on_open).pack(side=tk.LEFT, padx=4, pady=4)
        ttk.Button(toolbar, text="保存", command=self.on_save).pack(side=tk.LEFT, padx=4, pady=4)
        ttk.Button(toolbar, text="新增游戏", command=self.on_add_game).pack(side=tk.LEFT, padx=4, pady=4)
        ttk.Button(toolbar, text="删除选中", command=self.on_delete_game).pack(side=tk.LEFT, padx=4, pady=4)

        self.status_var = tk.StringVar(value="未打开文件")
        ttk.Label(toolbar, textvariable=self.status_var).pack(side=tk.RIGHT, padx=8)

        # 主区域：左右分栏
        main_pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True)

        # 左侧：game 列表
        left_frame = ttk.Frame(main_pane)
        main_pane.add(left_frame, weight=1)

        columns = ("id", "game", "file", "sort_by")
        self.tree = ttk.Treeview(
            left_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
        )
        self.tree.heading("id", text="ID")
        self.tree.heading("game", text="标题")
        self.tree.heading("file", text="文件")
        self.tree.heading("sort_by", text="排序")

        self.tree.column("id", width=150)
        self.tree.column("game", width=260)
        self.tree.column("file", width=260)
        self.tree.column("sort_by", width=80, anchor=tk.CENTER)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        # 右侧：用 Notebook 分三块
        right_frame = ttk.Frame(main_pane)
        main_pane.add(right_frame, weight=2)

        notebook = ttk.Notebook(right_frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 1: 基本信息表单
        form_frame = ttk.Frame(notebook, padding=8)
        notebook.add(form_frame, text="基本信息")

        form = ttk.Frame(form_frame)
        form.pack(fill=tk.BOTH, expand=True)

        self.fields = {}

        def add_field(label_text, key, row, multiline=False):
            ttk.Label(form, text=label_text).grid(row=row, column=0, sticky=tk.W, pady=4, padx=4)
            if multiline:
                txt = tk.Text(form, height=5, width=40, wrap=tk.WORD)
                txt.grid(row=row, column=1, sticky=tk.EW, pady=4, padx=4)
                self.fields[key] = txt
            else:
                var = tk.StringVar()
                state = "readonly" if key == "id" else "normal"
                entry = ttk.Entry(form, textvariable=var, state=state)
                entry.grid(row=row, column=1, sticky=tk.EW, pady=4, padx=4)
                self.fields[key] = var

        form.columnconfigure(1, weight=1)

        add_field("ID（只读）", "id", 0)
        add_field("游戏名 (game)", "game", 1)
        add_field("规范名 (canonical_name)", "canonical_name", 2)
        add_field("文件名 (file)", "file", 3)
        add_field("ROM 列表 (roms, 逗号分隔)", "roms", 4)
        add_field("排序号 (sort_by)", "sort_by", 5)
        add_field("开发者 (developer)", "developer", 6)
        add_field("简介 (description)", "description", 7, multiline=True)

        # 编辑时标记 dirty
        for key, widget in self.fields.items():
            if isinstance(widget, tk.StringVar):
                widget.trace_add("write", lambda *args: self._mark_dirty())
            elif isinstance(widget, tk.Text):
                widget.bind("<Key>", lambda event: self._mark_dirty())

        ttk.Button(
            form_frame,
            text="保存当前游戏修改到内存",
            command=self.on_apply_current
        ).pack(side=tk.BOTTOM, anchor=tk.E, pady=4, padx=8)

        # Tab 2: ROM Hashes 只读表格
        hash_frame = ttk.Frame(notebook, padding=8)
        notebook.add(hash_frame, text="ROM Hashes")

        hash_columns = ("rom_rel", "exists", "size", "md5_header", "sha256_full")
        self.hash_tree = ttk.Treeview(
            hash_frame,
            columns=hash_columns,
            show="headings",
            selectmode="browse",
        )
        self.hash_tree.heading("rom_rel", text="rom_rel")
        self.hash_tree.heading("exists", text="存在")
        self.hash_tree.heading("size", text="大小")
        self.hash_tree.heading("md5_header", text="md5_header")
        self.hash_tree.heading("sha256_full", text="sha256_full")

        self.hash_tree.column("rom_rel", width=260)
        self.hash_tree.column("exists", width=60, anchor=tk.CENTER)
        self.hash_tree.column("size", width=100, anchor=tk.E)
        self.hash_tree.column("md5_header", width=160)
        self.hash_tree.column("sha256_full", width=260)

        self.hash_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        hash_scrollbar = ttk.Scrollbar(hash_frame, orient=tk.VERTICAL, command=self.hash_tree.yview)
        self.hash_tree.configure(yscrollcommand=hash_scrollbar.set)
        hash_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Tab 3: Raw JSON 全字段只读
        raw_frame = ttk.Frame(notebook, padding=8)
        notebook.add(raw_frame, text="Raw JSON")

        self.raw_text = tk.Text(raw_frame, wrap=tk.NONE)
        self.raw_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        raw_scroll_y = ttk.Scrollbar(raw_frame, orient=tk.VERTICAL, command=self.raw_text.yview)
        raw_scroll_x = ttk.Scrollbar(raw_frame, orient=tk.HORIZONTAL, command=self.raw_text.xview)
        self.raw_text.configure(yscrollcommand=raw_scroll_y.set, xscrollcommand=raw_scroll_x.set)
        raw_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        raw_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)

    # ---------------- 事件处理 ----------------

    def _mark_dirty(self):
        if self._suspend_dirty or self.payload is None:
            return
        self.dirty = True
        self.status_var.set(f"{self.json_path} (已修改但未保存)")

    def on_open(self):
        # 默认指向 jsondb 目录
        initial_dir = JSONDB_DIR if JSONDB_DIR.exists() else Path.cwd()
        path = filedialog.askopenfilename(
            title="选择 jsondb 文件",
            initialdir=initial_dir,
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
        )
        if not path:
            return

        self.load_json(Path(path))

    def load_json(self, path: Path):
        try:
            with path.open("r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception as e:
            messagebox.showerror("错误", f"读取 JSON 失败：{e}")
            return

        self.json_path = path
        self.payload = payload
        self.games = payload.get("games", [])
        self.dirty = False

        self.status_var.set(str(self.json_path))
        self.populate_tree()
        self.clear_form()

    def populate_tree(self):
        self.tree.unbind("<<TreeviewSelect>>")

        self.tree.delete(*self.tree.get_children())
        for idx, g in enumerate(self.games):
            self.tree.insert(
                "",
                "end",
                iid=str(idx),
                values=(g.get("id", ""), g.get("game", ""), g.get("file", ""), g.get("sort_by", "")),
            )

        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

    def clear_form(self):
        self._suspend_dirty = True
        try:
            self.current_index = None
            for key, widget in self.fields.items():
                if isinstance(widget, tk.StringVar):
                    widget.set("")
                elif isinstance(widget, tk.Text):
                    widget.delete("1.0", tk.END)
            # 清空 hash / raw 视图
            if self.hash_tree is not None:
                self.hash_tree.delete(*self.hash_tree.get_children())
            if self.raw_text is not None:
                self.raw_text.delete("1.0", tk.END)
        finally:
            self._suspend_dirty = False

    def on_tree_select(self, event):
        if self._select_lock:
            return

        self._select_lock = True
        try:
            selection = self.tree.selection()
            if not selection:
                return

            idx_str = selection[0]
            idx = int(idx_str)
            if idx < 0 or idx >= len(self.games):
                return

            self.current_index = idx
            game = self.games[idx]
            self.load_game_to_form(game)
        finally:
            self._select_lock = False

    def _update_hash_view(self, game: dict):
        if self.hash_tree is None:
            return
        self.hash_tree.delete(*self.hash_tree.get_children())

        rom_hashes = game.get("rom_hashes") or []
        if not isinstance(rom_hashes, list):
            return

        for idx, h in enumerate(rom_hashes):
            rom_rel = h.get("rom_rel", "")
            exists = h.get("exists", False)
            size = h.get("size", "")
            md5_header = h.get("md5_header", "")
            sha256_full = h.get("sha256_full", "")

            self.hash_tree.insert(
                "",
                "end",
                iid=str(idx),
                values=(
                    rom_rel,
                    "✓" if exists else "",
                    size,
                    md5_header,
                    sha256_full,
                ),
            )

    def _update_raw_json(self, game: dict):
        if self.raw_text is None:
            return
        self.raw_text.delete("1.0", tk.END)
        try:
            raw = json.dumps(game, ensure_ascii=False, indent=2)
        except Exception as e:
            raw = f"<< JSON 序列化失败: {e} >>"
        self.raw_text.insert(tk.END, raw)

    def load_game_to_form(self, game: dict):
        self._suspend_dirty = True
        try:
            self._set_field("id", game.get("id", ""))
            self._set_field("game", game.get("game", ""))
            self._set_field("canonical_name", game.get("canonical_name", game.get("game", "")))
            self._set_field("file", game.get("file", ""))

            roms = game.get("roms")
            if isinstance(roms, list):
                roms_text = ", ".join(str(r) for r in roms)
            else:
                roms_text = ""
            self._set_field("roms", roms_text)

            self._set_field("sort_by", game.get("sort_by", ""))
            self._set_field("developer", game.get("developer", ""))
            self._set_field("description", game.get("description", ""))

            # 更新 ROM Hashes & Raw JSON 视图
            self._update_hash_view(game)
            self._update_raw_json(game)
        finally:
            self._suspend_dirty = False

    def on_apply_current(self):
        """将右侧表单的修改写回 self.games[current_index]，不写文件。"""
        if self.current_index is None:
            return
        if self.current_index < 0 or self.current_index >= len(self.games):
            return

        game = self.games[self.current_index]

        def get_text_field(key):
            widget = self.fields.get(key)
            if isinstance(widget, tk.StringVar):
                return widget.get().strip()
            elif isinstance(widget, tk.Text):
                return widget.get("1.0", tk.END).strip()
            return ""
        
        game_name = get_text_field("game") or game.get("game", "")
        game["game"] = game_name
        game["canonical_name"] = get_text_field("canonical_name") or game["game"]
        game["file"] = get_text_field("file") or game.get("file", "")

        # 确保 assets 存在
        if "assets" not in game or not isinstance(game["assets"], dict):
            game["assets"] = {}

        game["assets"]["box_front"] = f"media/{game_name}/boxfront.png"
        game["assets"]["logo"] = f"media/{game_name}/logo.png"
        game["assets"]["video"] = f"media/{game_name}/video.mp4"

        roms_text = get_text_field("roms")
        if roms_text:
            roms_list = [part.strip() for part in roms_text.split(",") if part.strip()]
        else:
            roms_list = []
        game["roms"] = roms_list

        sort_by = get_text_field("sort_by")
        if sort_by:
            game["sort_by"] = sort_by
        else:
            game.pop("sort_by", None)

        developer = get_text_field("developer")
        if developer:
            game["developer"] = developer
        elif "developer" in game:
            game.pop("developer", None)

        desc = get_text_field("description")
        if desc:
            game["description"] = desc
        elif "description" in game:
            game.pop("description", None)

        # 更新列表显示（左侧）
        self.populate_tree()
        if 0 <= self.current_index < len(self.games):
            self.tree.selection_set(str(self.current_index))
            self.tree.see(str(self.current_index))

        # 同步更新 Raw JSON / hashes 视图（因为 game 已变）
        self._update_hash_view(game)
        self._update_raw_json(game)

    def on_add_game(self):
        # 先应用当前编辑
        self.on_apply_current()

        new_game = {
            "id": "",
            "game": "新游戏",
            "canonical_name": "新游戏",
            "file": "",
            "roms": [],
            "assets": {
                "box_front": "media/新游戏/boxfront.png",
                "logo": "media/新游戏/logo.png",
                "video": "media/新游戏/video.mp4",
            }
        }
        self.games.append(new_game)
        self.populate_tree()

        new_index = len(self.games) - 1
        self.current_index = new_index
        self.load_game_to_form(new_game)
        self.tree.selection_set(str(new_index))
        self.tree.see(str(new_index))
        self._mark_dirty()

    def on_delete_game(self):
        if self.current_index is None:
            messagebox.showinfo("提示", "请先选择要删除的游戏。")
            return

        game = self.games[self.current_index]
        title = game.get("game", "")
        if not messagebox.askyesno("确认删除", f"确定要删除游戏：{title} ?"):
            return

        del self.games[self.current_index]
        self.current_index = None
        self.populate_tree()
        self.clear_form()
        self._mark_dirty()

    def on_save(self):
        if self.payload is None or self.json_path is None:
            messagebox.showinfo("提示", "请先打开一个 jsondb 文件。")
            return

        # 先把当前 game 的编辑应用到内存
        self.on_apply_current()

        self.payload["games"] = self.games

        try:
            with self.json_path.open("w", encoding="utf-8") as f:
                json.dump(self.payload, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("错误", f"保存失败：{e}")
            return

        self.dirty = False
        self.status_var.set(f"{self.json_path} (已保存)")
        messagebox.showinfo("成功", "已保存到原 JSON 文件。")


def main():
    app = JsonDbInspector()
    app.mainloop()


if __name__ == "__main__":
    main()
