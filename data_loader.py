"""扫描 data/ 目录并加载 BRFSS 数据文件（csv / xpt / sav）。"""
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent / "data"
EXTENSIONS = (".csv", ".xpt", ".sav")

_cache: pd.DataFrame | None = None


def find_data_file() -> Path | None:
    if not DATA_DIR.exists():
        return None
    for f in sorted(DATA_DIR.iterdir()):
        if f.suffix.lower() in EXTENSIONS and not f.name.startswith("."):
            return f
    return None


def _read(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix == ".xpt":
        return pd.read_sas(path, format="xport", encoding="utf-8")
    if suffix == ".sav":
        import pyreadstat

        return pyreadstat.read_sav(path)[0]
    raise ValueError(f"不支持的数据格式: {path.name}")


def load_df(force: bool = False) -> pd.DataFrame:
    global _cache
    if _cache is not None and not force:
        return _cache
    files = [
        f
        for f in sorted(DATA_DIR.iterdir())
        if f.suffix.lower() in EXTENSIONS and not f.name.startswith(".")
    ] if DATA_DIR.exists() else []
    if not files:
        raise FileNotFoundError(
            f"未在 {DATA_DIR} 下找到数据文件，请放入 .csv / .xpt / .sav 文件后重试"
        )
    features = [f for f in files if "feature" in f.name.lower()]
    targets = [f for f in files if "target" in f.name.lower() or "label" in f.name.lower()]
    if features and targets:  # 特征/标签分离存放的数据集，按行对齐合并
        df = pd.concat(
            [_read(features[0]).reset_index(drop=True), _read(targets[0]).reset_index(drop=True)],
            axis=1,
        )
    else:
        df = _read(files[0])
    _cache = df
    return df


def schema_text(df: pd.DataFrame) -> str:
    """生成给 LLM 看的数据集概览（有长度上限，防止超上下文）。"""
    lines = [f"shape: {df.shape[0]} 行 x {df.shape[1]} 列", "columns:"]
    for col in df.columns:
        n_missing = int(df[col].isna().sum())
        if pd.api.types.is_numeric_dtype(df[col]):
            stats = df[col].describe().round(3).to_dict()
            info = (
                f"数值型, 缺失{n_missing}, "
                f"min={stats.get('min')}, max={stats.get('max')}, mean={stats.get('mean')}"
            )
        else:
            top = df[col].value_counts().head(5)
            info = f"分类型, 缺失{n_missing}, 取值示例: {dict(top)}"
        lines.append(f"- {col}: {info}")
    return "\n".join(lines[:80])
