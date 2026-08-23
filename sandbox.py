"""受限代码沙箱：隔离的 exec 环境 + 超时 + 图表捕获。

安全边界（demo 级）：
- 只允许白名单内的模块导入（pandas/numpy/matplotlib/scipy/sklearn 等）
- 移除危险内建函数（open/exec/eval/compile/__import__ 等）
- 单次执行超时上限
生产环境应换成独立容器/子进程隔离，见 README「安全设计」。
"""
import builtins
import contextlib
import io
import threading
import traceback

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ALLOWED_MODULES = {
    "pandas", "numpy", "matplotlib", "math", "statistics", "scipy",
    "sklearn", "datetime", "collections", "itertools", "functools",
}

SAFE_BUILTINS = {
    name: getattr(builtins, name)
    for name in (
        "abs", "all", "any", "bool", "dict", "divmod", "enumerate", "filter",
        "float", "format", "frozenset", "hash", "hex", "int", "isinstance",
        "issubclass", "iter", "len", "list", "map", "max", "min", "next",
        "object", "oct", "ord", "pow", "print", "range", "repr", "reversed",
        "round", "set", "slice", "sorted", "str", "sum", "tuple", "type",
        "zip", "True", "False", "None",
        "Exception", "ValueError", "TypeError", "KeyError", "IndexError",
        "AttributeError", "RuntimeError", "ZeroDivisionError",
        "ArithmeticError", "StopIteration", "Warning", "ImportError",
    )
}


def _checked_import(name, globals=None, locals=None, fromlist=(), level=0):
    root = name.split(".")[0]
    if root not in ALLOWED_MODULES:
        raise ImportError(f"沙箱禁止导入模块: {name}")
    return builtins.__import__(name, globals, locals, fromlist, level)


class SandboxResult:
    def __init__(self):
        self.ok = False
        self.stdout = ""
        self.error = ""
        self.result = ""
        self.figures = []  # list[PIL.Image.Image]

    def to_tool_text(self, max_chars: int = 4000) -> str:
        parts = [f"执行{'成功' if self.ok else '失败'}"]
        if self.stdout:
            parts.append(f"stdout:\n{self.stdout[:max_chars]}")
        if self.error:
            parts.append(f"error:\n{self.error[:2000]}")
        if self.result:
            parts.append(f"return:\n{str(self.result)[:1000]}")
        if self.figures:
            parts.append(f"生成了 {len(self.figures)} 张图表（已在前端展示，含 plt.show() 输出）")
        return "\n".join(parts)


def run_code(code: str, df, timeout: int = 30) -> SandboxResult:
    """在受限命名空间中执行 code，df 以变量名 df 注入。"""
    from PIL import Image

    res = SandboxResult()
    namespace = {
        "__builtins__": {**SAFE_BUILTINS, "__import__": _checked_import},
        "__import__": _checked_import,
        "df": df,
        "pd": __import__("pandas"),
        "np": __import__("numpy"),
        "plt": plt,
    }
    buffer = io.StringIO()
    plt.close("all")

    def target():
        try:
            with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
                # 代码最后一行的表达式值（尽量保留 return 信息）
                try:
                    import ast

                    tree = ast.parse(code)
                    last = tree.body[-1] if tree.body else None
                    if isinstance(last, ast.Expr):
                        compiled = compile(
                            ast.Module(body=tree.body[:-1], type_ignores=[]), "<sandbox>", "exec"
                        )
                        exec(compiled, namespace)
                        value = eval(  # noqa: S307
                            compile(ast.Expression(last.value), "<sandbox>", "eval"), namespace
                        )
                        res.result = repr(value)
                    else:
                        exec(compile(tree, "<sandbox>", "exec"), namespace)
                except SyntaxError:
                    exec(code, namespace)
            res.ok = True
        except Exception:
            res.error = traceback.format_exc(limit=5)

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        res.error = f"执行超时（>{timeout}s），已终止返回"
    res.stdout = buffer.getvalue()

    for num in plt.get_fignums():
        fig = plt.figure(num)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
        buf.seek(0)
        res.figures.append(Image.open(buf).copy())
    plt.close("all")
    return res
