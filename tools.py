"""Agent 工具定义（DeepSeek function calling 格式）与执行器。"""
from data_loader import load_df, schema_text
from sandbox import run_code

TOOLS_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "get_dataset_schema",
            "description": "获取当前数据集的行列数、每列的类型、缺失值、取值分布等概览信息。开始任何分析前应先调用一次。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_analysis",
            "description": (
                "在受限沙箱中执行 Python 数据分析代码，可用变量: df(数据集), pd, np, plt。"
                "plt 绘图会被自动捕获并展示给用户，无需 savefig。代码需在 30 秒内完成。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "要执行的 Python 代码，df 为 pandas.DataFrame",
                    }
                },
                "required": ["code"],
            },
        },
    },
]


def execute_tool(name: str, arguments: dict):
    """执行工具，返回 (给LLM的文本结果, 给前端的图片列表)。"""
    if name == "get_dataset_schema":
        df = load_df()
        return schema_text(df), []
    if name == "run_analysis":
        df = load_df()
        result = run_code(arguments["code"], df)
        return result.to_tool_text(), result.figures
    raise ValueError(f"未知工具: {name}")
