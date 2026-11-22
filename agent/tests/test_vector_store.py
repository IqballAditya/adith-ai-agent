import os
import pytest
from agent.parser import ASTParser, CodeSymbol
from agent.memory.vector_store import VectorStore, SearchResult
from agent.indexer import CodebaseIndexer


@pytest.fixture
def memory_store():
    return VectorStore(storage_path=":memory:", collection_name="test_codebase")


def test_vector_store_initialization(memory_store):
    assert memory_store.collection_name == "test_codebase"
    assert memory_store.client.collection_exists("test_codebase")


def test_index_symbols_and_search(memory_store):
    symbols = [
        CodeSymbol(
            name="calculate_total",
            symbol_type="function",
            start_line=1,
            end_line=5,
            signature="def calculate_total(items: list[float]) -> float",
            raw_code="def calculate_total(items: list[float]) -> float:\n    return sum(items)",
            language="python",
        ),
        CodeSymbol(
            name="AuthService",
            symbol_type="class",
            start_line=10,
            end_line=25,
            signature="class AuthService",
            raw_code="class AuthService:\n    def login(self, user, pwd):\n        pass",
            language="python",
        ),
        CodeSymbol(
            name="format_currency",
            symbol_type="function",
            start_line=30,
            end_line=35,
            signature="def format_currency(amount: float) -> str",
            raw_code="def format_currency(amount: float) -> str:\n    return f'${amount:.2f}'",
            language="python",
        ),
    ]

    indexed_count = memory_store.index_symbols(
        workspace_id="ws_1",
        symbols=symbols,
        file_path="src/billing.py",
    )
    assert indexed_count == 3

    # Semantic / keyword search for calculate_total
    results = memory_store.search(workspace_id="ws_1", query="calculate total", limit=5)
    assert len(results) > 0
    top = results[0]
    assert isinstance(top, SearchResult)
    assert top.symbol_name == "calculate_total"
    assert top.symbol_type == "function"
    assert top.file_path == "src/billing.py"
    assert top.start_line == 1
    assert top.end_line == 5
    assert "return sum(items)" in top.raw_code
    assert top.language == "python"
    assert top.score > 0


def test_search_workspace_isolation(memory_store):
    sym_ws1 = [
        CodeSymbol(
            name="render_header",
            symbol_type="function",
            start_line=1,
            end_line=4,
            signature="function renderHeader()",
            raw_code="function renderHeader() { return '<header/>'; }",
            language="javascript",
        )
    ]
    sym_ws2 = [
        CodeSymbol(
            name="render_footer",
            symbol_type="function",
            start_line=1,
            end_line=4,
            signature="function renderFooter()",
            raw_code="function renderFooter() { return '<footer/>'; }",
            language="javascript",
        )
    ]

    memory_store.index_symbols("ws_alpha", sym_ws1, "src/header.js")
    memory_store.index_symbols("ws_beta", sym_ws2, "src/footer.js")

    res_alpha = memory_store.search("ws_alpha", query="render", limit=10)
    assert len(res_alpha) == 1
    assert res_alpha[0].symbol_name == "render_header"

    res_beta = memory_store.search("ws_beta", query="render", limit=10)
    assert len(res_beta) == 1
    assert res_beta[0].symbol_name == "render_footer"


def test_search_filter_by_symbol_type(memory_store):
    symbols = [
        CodeSymbol(
            name="OrderModel",
            symbol_type="class",
            start_line=1,
            end_line=10,
            signature="class OrderModel",
            raw_code="class OrderModel:\n    pass",
            language="python",
        ),
        CodeSymbol(
            name="process_order",
            symbol_type="function",
            start_line=12,
            end_line=20,
            signature="def process_order(order: OrderModel)",
            raw_code="def process_order(order: OrderModel):\n    return True",
            language="python",
        ),
    ]
    memory_store.index_symbols("ws_store", symbols, "src/orders.py")

    # Search with symbol_type filter
    class_results = memory_store.search("ws_store", query="order", symbol_type="class")
    assert all(r.symbol_type == "class" for r in class_results)
    assert any(r.symbol_name == "OrderModel" for r in class_results)

    func_results = memory_store.search("ws_store", query="order", symbol_type="function")
    assert all(r.symbol_type == "function" for r in func_results)
    assert any(r.symbol_name == "process_order" for r in func_results)


def test_codebase_indexer(tmp_path):
    # Setup test workspace
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    py_file = src_dir / "calculator.py"
    py_file.write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n\ndef multiply(a: int, b: int) -> int:\n    return a * b\n",
        encoding="utf-8",
    )

    ts_file = src_dir / "service.ts"
    ts_file.write_text(
        "interface UserProfile {\n  id: string;\n  name: string;\n}\n\nclass UserService {\n  getUser(): UserProfile {\n    return { id: '1', name: 'Alice' };\n  }\n}\n",
        encoding="utf-8",
    )

    # Ignored directories
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "hook.py").write_text("def hook(): pass", encoding="utf-8")

    store = VectorStore(storage_path=":memory:", collection_name="indexer_test")
    indexer = CodebaseIndexer(vector_store=store)

    result = indexer.index_workspace(str(tmp_path), workspace_id="ws_idx")

    assert result["workspace_id"] == "ws_idx"
    assert result["files_indexed"] >= 2
    assert result["symbols_indexed"] >= 2
    assert result["status"] == "success"

    # Search for indexed symbols
    search_res = store.search(workspace_id="ws_idx", query="add numbers", limit=5)
    assert len(search_res) > 0
    names = [r.symbol_name for r in search_res]
    assert "add" in names

    # Verify .git hook was skipped
    hook_res = store.search(workspace_id="ws_idx", query="hook", limit=5)
    hook_names = [r.symbol_name for r in hook_res]
    assert "hook" not in hook_names


def test_empty_indexing_and_invalid_path(tmp_path):
    store = VectorStore(storage_path=":memory:", collection_name="empty_test")
    assert store.index_symbols("ws_empty", []) == 0

    indexer = CodebaseIndexer(vector_store=store)
    res = indexer.index_workspace(str(tmp_path / "nonexistent"), "ws_none")
    assert res["status"] == "error"
    assert res["files_indexed"] == 0


def test_file_storage_persistence(tmp_path):
    storage_dir = str(tmp_path / "qdrant_data")
    store = VectorStore(storage_path=storage_dir, collection_name="persistent_chunks")
    sym = [
        CodeSymbol(
            name="init_config",
            symbol_type="function",
            start_line=1,
            end_line=5,
            signature="def init_config()",
            raw_code="def init_config(): return {}",
            language="python",
        )
    ]
    store.index_symbols("ws_persist", sym, "config.py")
    store.close()

    # Reopen store with same storage path
    reopened = VectorStore(storage_path=storage_dir, collection_name="persistent_chunks")
    try:
        results = reopened.search("ws_persist", query="init config")
        assert len(results) > 0
        assert results[0].symbol_name == "init_config"
    finally:
        reopened.close()


def test_index_symbols_batching(memory_store):
    # Test batch upserting over 100 symbols (e.g. 250 symbols)
    symbols = [
        CodeSymbol(
            name=f"func_{i}",
            symbol_type="function",
            start_line=i * 5,
            end_line=i * 5 + 4,
            signature=f"def func_{i}()",
            raw_code=f"def func_{i}():\n    return {i}",
            language="python",
        )
        for i in range(250)
    ]
    indexed_count = memory_store.index_symbols(
        workspace_id="ws_batch",
        symbols=symbols,
        file_path="src/large_file.py",
    )
    assert indexed_count == 250
    res = memory_store.search("ws_batch", query="func_150", limit=5)
    assert len(res) > 0
    assert any("func_150" in r.symbol_name for r in res)

