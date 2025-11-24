#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
简单的 jsondb Inspector（基于 Tkinter）

功能：
- 打开 jsondb/<platform>.json
- 左侧列表查看 games 列表
- 右侧编辑常用字段（game / canonical_name / file / roms / sort_by / developer / description）
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
        self.geometry("1000x600")

        self.json_path: Path | None = None
        self.payload: dict | None = None
        self.games: list[dict] = []
        self.current_index: int | None = None
        self.dirty: bool = False
        self._suspend_dirty = False
        self._select_lock = False
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
        self.tree.column("game", width=220)
        self.tree.column("file", width=220)
        self.tree.column("sort_by", width=80, anchor=tk.CENTER)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        # 右侧：编辑表单
        right_frame = ttk.Frame(main_pane, padding=8)
        main_pane.add(right_frame, weight=1)

        form = ttk.Frame(right_frame)
        form.pack(fill=tk.BOTH, expand=True)

        self.fields = {}

        def add_field(label_text, key, row, multiline=False):
            ttk.Label(form, text=label_text).grid(row=row, column=0, sticky=tk.W, pady=4)
            if multiline:
                txt = tk.Text(form, height=5, width=40, wrap=tk.WORD)
                txt.grid(row=row, column=1, sticky=tk.EW, pady=4)
                self.fields[key] = txt
            else:
                var = tk.StringVar()
                state = "readonly" if key == "id" else "normal"
                entry = ttk.Entry(form, textvariable=var, state=state)
                entry.grid(row=row, column=1, sticky=tk.EW, pady=4)
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

        # 保存当前 game 的按钮
        ttk.Button(right_frame, text="保存当前游戏修改到内存", command=self.on_apply_current).pack(
            side=tk.BOTTOM, anchor=tk.E, pady=4
        )

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
            self.tree.insert("", "end", iid=str(idx),
                             values=(g.get("id",""), g.get("game",""), g.get("file",""), g.get("sort_by","")))

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

        # game_id = get_text_field("id")

        # if game_id:
        #     game["id"] = game_id

        game["game"] = get_text_field("game") or game.get("game", "")
        game["canonical_name"] = get_text_field("canonical_name") or game["game"]
        game["file"] = get_text_field("file") or game.get("file", "")

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

        # 更新列表显示
        self.populate_tree()
        if 0 <= self.current_index < len(self.games):
            self.tree.selection_set(str(self.current_index))
            self.tree.see(str(self.current_index))


    def on_add_game(self):
        # 先应用当前编辑
        self.on_apply_current()

        new_game = {
            "id": "",
            "game": "新游戏",
            "canonical_name": "新游戏",
            "file": "",
            "roms": [],
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
