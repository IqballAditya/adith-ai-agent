import sys
from pathlib import Path

# Ensure agent directory and repository root are on sys.path
AGENT_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = AGENT_ROOT.parent
for p in [str(REPO_ROOT), str(AGENT_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest

try:
    from agent.parser.ast_parser import ASTParser, CodeSymbol
except ImportError:
    from parser.ast_parser import ASTParser, CodeSymbol


def test_go_symbol_extraction():
    go_code = """package main

type User struct {
    Name string
    Age  int
}

type Reader interface {
    Read(p []byte) (n int, err error)
}

func Add(a int, b int) int {
    return a + b
}

func (u *User) GetName() string {
    return u.Name
}
"""
    symbols = ASTParser.parse_code(go_code, "go")
    assert len(symbols) == 4

    by_name = {s.name: s for s in symbols}

    # Struct
    assert "User" in by_name
    assert by_name["User"].symbol_type == "struct"
    assert by_name["User"].language == "go"
    assert by_name["User"].start_line == 3
    assert "User struct" in by_name["User"].signature
    assert "type User struct" in by_name["User"].raw_code

    # Interface
    assert "Reader" in by_name
    assert by_name["Reader"].symbol_type == "interface"
    assert by_name["Reader"].language == "go"
    assert by_name["Reader"].start_line == 8
    assert "Reader interface" in by_name["Reader"].signature
    assert "type Reader interface" in by_name["Reader"].raw_code

    # Function
    assert "Add" in by_name
    assert by_name["Add"].symbol_type == "function"
    assert by_name["Add"].language == "go"
    assert by_name["Add"].start_line == 12
    assert "func Add(a int, b int) int" in by_name["Add"].signature
    assert "return a + b" in by_name["Add"].raw_code

    # Method
    assert "GetName" in by_name
    assert by_name["GetName"].symbol_type == "method"
    assert by_name["GetName"].language == "go"
    assert by_name["GetName"].start_line == 16
    assert "func (u *User) GetName() string" in by_name["GetName"].signature
    assert "return u.Name" in by_name["GetName"].raw_code


def test_go_grouped_type_declarations():
    go_code = """package main

type (
    Config struct {
        Port int
    }
    Handler interface {
        Serve()
    }
)
"""
    symbols = ASTParser.parse_code(go_code, "go")
    assert len(symbols) == 2
    by_name = {s.name: s for s in symbols}

    assert "Config" in by_name
    assert by_name["Config"].symbol_type == "struct"
    assert by_name["Config"].start_line == 4

    assert "Handler" in by_name
    assert by_name["Handler"].symbol_type == "interface"
    assert by_name["Handler"].start_line == 7


def test_python_symbol_extraction():
    python_code = '''"""Module docstring"""

class Invoice:
    def __init__(self, invoice_id: str, amount: float):
        self.invoice_id = invoice_id
        self.amount = amount

    def get_summary(self) -> str:
        return f"Invoice {self.invoice_id}: ${self.amount}"

def calculate_tax(amount: float, rate: float = 0.1) -> float:
    return amount * rate

async def process_payment(invoice: Invoice) -> bool:
    return True
'''
    symbols = ASTParser.parse_code(python_code, "python")
    assert len(symbols) == 5

    by_name = {s.name: s for s in symbols}

    # Class
    assert "Invoice" in by_name
    assert by_name["Invoice"].symbol_type == "class"
    assert by_name["Invoice"].language == "python"
    assert by_name["Invoice"].start_line == 3
    assert "class Invoice" in by_name["Invoice"].signature

    # Methods
    assert "__init__" in by_name
    assert by_name["__init__"].symbol_type == "method"
    assert by_name["__init__"].language == "python"
    assert by_name["__init__"].start_line == 4

    assert "get_summary" in by_name
    assert by_name["get_summary"].symbol_type == "method"
    assert by_name["get_summary"].language == "python"
    assert by_name["get_summary"].start_line == 8

    # Functions
    assert "calculate_tax" in by_name
    assert by_name["calculate_tax"].symbol_type == "function"
    assert by_name["calculate_tax"].language == "python"
    assert by_name["calculate_tax"].start_line == 11
    assert "def calculate_tax" in by_name["calculate_tax"].signature

    assert "process_payment" in by_name
    assert by_name["process_payment"].symbol_type == "function"
    assert by_name["process_payment"].language == "python"
    assert by_name["process_payment"].start_line == 14
    assert "process_payment" in by_name["process_payment"].signature


def test_python_decorated_symbols():
    python_code = """
@dataclass
class Service:
    name: str

    @property
    def service_name(self) -> str:
        return self.name
"""
    symbols = ASTParser.parse_code(python_code, "python")
    by_name = {s.name: s for s in symbols}
    assert "Service" in by_name
    assert by_name["Service"].symbol_type == "class"
    assert "service_name" in by_name
    assert by_name["service_name"].symbol_type == "method"


def test_typescript_symbol_extraction():
    ts_code = """export interface WorkerConfig {
    concurrency: number;
    timeoutMs: number;
}

export class TaskRunner {
    private isRunning: boolean = false;

    constructor(private config: WorkerConfig) {}

    public execute(taskName: string): Promise<void> {
        return Promise.resolve();
    }
}

export function computeStats(values: number[]): number {
    return values.reduce((a, b) => a + b, 0);
}

export const formatOutput = (summary: string): string => {
    return `Output: ${summary}`;
};
"""
    symbols = ASTParser.parse_code(ts_code, "typescript")
    by_name = {s.name: s for s in symbols}

    # Interface
    assert "WorkerConfig" in by_name
    assert by_name["WorkerConfig"].symbol_type == "interface"
    assert by_name["WorkerConfig"].language == "typescript"
    assert by_name["WorkerConfig"].start_line == 1

    # Class
    assert "TaskRunner" in by_name
    assert by_name["TaskRunner"].symbol_type == "class"
    assert by_name["TaskRunner"].language == "typescript"
    assert by_name["TaskRunner"].start_line == 6

    # Methods
    assert "constructor" in by_name
    assert by_name["constructor"].symbol_type == "method"
    assert by_name["constructor"].language == "typescript"

    assert "execute" in by_name
    assert by_name["execute"].symbol_type == "method"
    assert by_name["execute"].language == "typescript"

    # Function declaration
    assert "computeStats" in by_name
    assert by_name["computeStats"].symbol_type == "function"
    assert by_name["computeStats"].language == "typescript"

    # Arrow function declaration
    assert "formatOutput" in by_name
    assert by_name["formatOutput"].symbol_type == "function"
    assert by_name["formatOutput"].language == "typescript"


def test_javascript_symbol_extraction():
    js_code = """
function calculateTotal(items) {
    return items.length;
}

const formatPrice = (p) => `$${p}`;
"""
    symbols = ASTParser.parse_code(js_code, "javascript")
    by_name = {s.name: s for s in symbols}
    assert "calculateTotal" in by_name
    assert by_name["calculateTotal"].symbol_type == "function"
    assert by_name["calculateTotal"].language == "javascript"
    assert "formatPrice" in by_name
    assert by_name["formatPrice"].symbol_type == "function"
    assert by_name["formatPrice"].language == "javascript"


def test_go_type_alias_not_falsified_as_struct():
    go_code = """package main
type UserID string
type Status int
type User struct {
    ID UserID
}
"""
    symbols = ASTParser.parse_code(go_code, "go")
    by_name = {s.name: s for s in symbols}
    assert "User" in by_name
    assert by_name["User"].symbol_type == "struct"
    # Ensure type alias UserID and Status are not falsely classified as struct
    assert "UserID" not in by_name
    assert "Status" not in by_name


def test_empty_and_whitespace_code():
    assert ASTParser.parse_code("", "python") == []
    assert ASTParser.parse_code("   \\n\\t  ", "go") == []
    assert ASTParser.parse_code("// Just a comment\\n", "typescript") == []


def test_malformed_syntax_graceful_recovery():
    malformed_py = """def broken_function(a, :
    print("incomplete")

def valid_function(x: int) -> int:
    return x * 2
"""
    symbols = ASTParser.parse_code(malformed_py, "python")
    # Tree-sitter or fallback should still extract valid_function without raising
    names = [s.name for s in symbols]
    assert "valid_function" in names


def test_unsupported_language_regex_fallback():
    rust_like_code = """fn calculate_area(width: u32, height: u32) -> u32 {
    width * height
}

struct Rectangle {
    width: u32,
    height: u32,
}
"""
    # Should not crash on unknown language
    symbols = ASTParser.parse_code(rust_like_code, "rust")
    assert isinstance(symbols, list)
    by_name = {s.name: s for s in symbols}
    assert "calculate_area" in by_name
    assert by_name["calculate_area"].symbol_type == "function"
    assert "Rectangle" in by_name
    assert by_name["Rectangle"].symbol_type == "struct"


def test_direct_regex_fallback():
    go_snippet = """func MyHelper(val string) bool {
    return len(val) > 0
}
"""
    symbols = ASTParser._regex_fallback(go_snippet, "go")
    assert len(symbols) == 1
    assert symbols[0].name == "MyHelper"
    assert symbols[0].symbol_type == "function"
