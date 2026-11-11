from mcp.server import MCPServer
from datetime import datetime
import statistics
import pandas as pd
from io import StringIO


# Initialize MCP Server
mcp = MCPServer("SmartTools")

@mcp.tool()
def add(a: float, b: float) -> float:
    """Add two numbers."""
    return a + b

@mcp.tool()
def subtract(a: float, b: float) -> float:
    """Subtract the second number from the first."""
    return a - b

@mcp.tool()
def multiply(a: float, b: float) -> float:
    """Multiply two numbers."""
    return a * b


@mcp.tool()
def divide(a: float, b: float) -> str:
    """Divide the first number by the second."""
    if b == 0:
        return "Error: Cannot divide by zero."

    return str(a / b)


@mcp.tool()
def get_current_datetime() -> str:
    """Get the current local date and time."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


@mcp.tool()
def calculate_statistics(numbers: list[float]) -> dict:
    """
    Calculate descriptive statistics for a list of numbers.

    Returns count, mean, median, minimum, maximum
    and population standard deviation.
    """
    if not numbers:
        return {"error": "The list cannot be empty."}

    return {
        "count": len(numbers),
        "mean": statistics.mean(numbers),
        "median": statistics.median(numbers),
        "minimum": min(numbers),
        "maximum": max(numbers),
        "standard_deviation": statistics.pstdev(numbers)
    }


@mcp.tool()
def analyze_csv(csv_content: str) -> dict:
    """
    Analyze CSV data and return basic information.
    Use \\n to separate rows.
    """

    # Convert escaped newline characters into actual line breaks
    csv_text = csv_content.replace("\\n", "\n")

    df = pd.read_csv(StringIO(csv_text))

    if df.empty:
        return {"error": "CSV contains no data rows."}

    return {
        "rows": len(df),
        "columns": len(df.columns),
        "column_names": df.columns.tolist()
    }

if __name__ == "__main__":
    mcp.run(transport="stdio")
