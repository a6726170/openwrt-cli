"""输出格式化 — 支持 text / json / compact 三种格式"""
import json
import copy


class OutputFormatter:
    def __init__(self, format_type="text", pretty=True):
        self.format_type = format_type
        self.pretty = pretty

    def dump(self, data) -> str:
        """将数据对象格式化为字符串"""
        if data is None:
            return ""

        # 统一处理：如果是已渲染的字符串，直接返回
        if isinstance(data, str):
            return data

        if self.format_type == "json":
            return self._to_json(data)
        elif self.format_type == "compact":
            return self._to_compact(data)
        else:
            return self._to_text(data)

    def _to_json(self, data) -> str:
        kwargs = {"indent": 2, "ensure_ascii": False}
        if not self.pretty:
            kwargs = {"indent": None, "ensure_ascii": False, "separators": (",", ":")}
        return json.dumps(data, **kwargs)

    def _to_compact(self, data) -> str:
        """紧凑 JSON（无缩进）"""
        return json.dumps(data, ensure_ascii=False, separators=(",", ":"))

    def _to_text(self, data) -> str:
        """人类可读文本格式"""
        if isinstance(data, dict):
            return self._dict_to_text(data, indent=0)
        elif isinstance(data, list):
            return "\n".join(self._item_to_text(item) for item in data)
        else:
            return str(data)

    def _dict_to_text(self, d: dict, indent: int = 0) -> str:
        lines = []
        prefix = "  " * indent
        for key, value in d.items():
            if isinstance(value, dict):
                lines.append(f"{prefix}{key}:")
                lines.append(self._dict_to_text(value, indent + 1))
            elif isinstance(value, list):
                lines.append(f"{prefix}{key}:")
                for item in value:
                    if isinstance(item, dict):
                        lines.append(self._dict_to_text(item, indent + 1))
                    else:
                        lines.append(f"{prefix}  - {item}")
            else:
                lines.append(f"{prefix}{key}: {value}")
        return "\n".join(lines)

    def _item_to_text(self, item) -> str:
        if isinstance(item, dict):
            return self._dict_to_text(item)
        return str(item)

    def header(self, title: str) -> str:
        """带装饰的标题"""
        line = "=" * 60
        if self.format_type == "json":
            return self._to_json({"section": title})
        return f"\n{line}\n{title}\n{line}"

    def ok(self, msg: str) -> str:
        if self.format_type == "json":
            return self._to_json({"status": "ok", "message": msg})
        return f"✅ {msg}"

    def error(self, msg: str) -> str:
        if self.format_type == "json":
            return self._to_json({"status": "error", "message": msg})
        return f"❌ {msg}"

    def warn(self, msg: str) -> str:
        if self.format_type == "json":
            return self._to_json({"status": "warn", "message": msg})
        return f"⚠️  {msg}"

    def table(self, headers: list, rows: list) -> str:
        """
        文本表格输出
        headers: ["列1", "列2"]
        rows: [["a", "b"], ["c", "d"]]
        """
        if self.format_type != "text":
            return self._to_json({"headers": headers, "rows": rows})

        col_widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(cell)))

        def fmt_row(cells):
            return " | ".join(str(c).ljust(w) for c, w in zip(cells, col_widths))

        sep = "-+-".join("-" * w for w in col_widths)
        lines = [
            fmt_row(headers),
            sep,
            *[fmt_row(row) for row in rows],
        ]
        return "\n".join(lines)