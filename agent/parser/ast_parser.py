from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

@dataclass
class CodeSymbol:
    name: str
    symbol_type: str  # 'function', 'method', 'class', 'struct', 'interface'
    start_line: int
    end_line: int
    signature: str
    raw_code: str
    language: str


_LANG_CACHE: dict[str, Any] = {}
_PARSER_CACHE: dict[str, Any] = {}
_TREE_SITTER_INIT_DONE = False


def _init_tree_sitter() -> None:
    global _TREE_SITTER_INIT_DONE
    if _TREE_SITTER_INIT_DONE:
        return
    _TREE_SITTER_INIT_DONE = True

    try:
        from tree_sitter import Language, Parser

        try:
            import tree_sitter_python
            lang_py = Language(tree_sitter_python.language())
            _LANG_CACHE["python"] = lang_py
            _PARSER_CACHE["python"] = Parser(lang_py)
        except Exception:
            pass

        try:
            import tree_sitter_go
            lang_go = Language(tree_sitter_go.language())
            _LANG_CACHE["go"] = lang_go
            _PARSER_CACHE["go"] = Parser(lang_go)
        except Exception:
            pass

        try:
            import tree_sitter_typescript
            lang_ts = Language(tree_sitter_typescript.language_typescript())
            _LANG_CACHE["typescript"] = lang_ts
            _PARSER_CACHE["typescript"] = Parser(lang_ts)
            _LANG_CACHE["javascript"] = lang_ts
            _PARSER_CACHE["javascript"] = Parser(lang_ts)
        except Exception:
            pass
    except Exception:
        pass


def _normalize_lang(language: str) -> str:
    lang = (language or "").strip().lower()
    if lang in ("python", "py", "python3"):
        return "python"
    if lang in ("go", "golang"):
        return "go"
    if lang in ("typescript", "ts", "tsx"):
        return "typescript"
    if lang in ("javascript", "js", "jsx", "mjs", "cjs"):
        return "javascript"
    return lang


def _calc_lines(node: Any) -> tuple[int, int]:
    start_line = node.start_point[0] + 1
    end_line = node.end_point[0] if (node.end_point[1] == 0 and node.end_point[0] > node.start_point[0]) else node.end_point[0] + 1
    return start_line, end_line


def _extract_sig_from_body(node: Any, body_node: Optional[Any], code_bytes: bytes) -> str:
    if body_node is not None and body_node.start_byte >= node.start_byte:
        sig_raw = code_bytes[node.start_byte:body_node.start_byte].decode("utf-8", errors="replace")
        return sig_raw.strip().rstrip(":{").strip()
    # Fallback to first line
    text = code_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
    first_line = text.splitlines()[0] if text else ""
    return first_line.strip().rstrip(":{").strip()


class ASTParser:
    @classmethod
    def parse_code(cls, code: str, language: str) -> list[CodeSymbol]:
        if not code or not code.strip():
            return []

        norm_lang = _normalize_lang(language)
        _init_tree_sitter()

        parser = _PARSER_CACHE.get(norm_lang)
        if parser is None:
            return cls._regex_fallback(code, norm_lang or language)

        try:
            code_bytes = code.encode("utf-8")
            tree = parser.parse(code_bytes)
            root = tree.root_node

            if norm_lang == "go":
                symbols = cls._parse_go(root, code_bytes)
            elif norm_lang == "python":
                symbols = cls._parse_python(root, code_bytes)
            elif norm_lang in ("typescript", "javascript"):
                symbols = cls._parse_typescript(root, code_bytes, norm_lang)
            else:
                symbols = []

            # If tree-sitter couldn't extract any symbols and had error, try regex fallback
            if not symbols and root.has_error:
                return cls._regex_fallback(code, norm_lang or language)

            return symbols
        except Exception:
            return cls._regex_fallback(code, norm_lang or language)

    @classmethod
    def _parse_go(cls, root: Any, code_bytes: bytes) -> list[CodeSymbol]:
        symbols: list[CodeSymbol] = []

        for node in root.children:
            if node.type == "function_declaration":
                name_node = node.child_by_field_name("name")
                if not name_node:
                    continue
                name = name_node.text.decode("utf-8", errors="replace")
                body = node.child_by_field_name("body")
                start_l, end_l = _calc_lines(node)
                sig = _extract_sig_from_body(node, body, code_bytes)
                raw = node.text.decode("utf-8", errors="replace")
                symbols.append(CodeSymbol(
                    name=name,
                    symbol_type="function",
                    start_line=start_l,
                    end_line=end_l,
                    signature=sig,
                    raw_code=raw,
                    language="go",
                ))

            elif node.type == "method_declaration":
                name_node = node.child_by_field_name("name")
                if not name_node:
                    continue
                name = name_node.text.decode("utf-8", errors="replace")
                body = node.child_by_field_name("body")
                start_l, end_l = _calc_lines(node)
                sig = _extract_sig_from_body(node, body, code_bytes)
                raw = node.text.decode("utf-8", errors="replace")
                symbols.append(CodeSymbol(
                    name=name,
                    symbol_type="method",
                    start_line=start_l,
                    end_line=end_l,
                    signature=sig,
                    raw_code=raw,
                    language="go",
                ))

            elif node.type == "type_declaration":
                # A type_declaration may contain one or more type_spec nodes
                specs = [c for c in node.children if c.type == "type_spec"]
                single_spec = len(specs) == 1
                for spec in specs:
                    name_node = spec.child_by_field_name("name")
                    type_node = spec.child_by_field_name("type")
                    if not name_node:
                        continue
                    name = name_node.text.decode("utf-8", errors="replace")
                    type_str = type_node.type if type_node else ""
                    if type_str == "struct_type":
                        sym_type = "struct"
                    elif type_str == "interface_type":
                        sym_type = "interface"
                    else:
                        sym_type = "struct"

                    start_l, end_l = _calc_lines(node if single_spec else spec)
                    sig = f"type {name} {sym_type}"
                    raw = (node if single_spec else spec).text.decode("utf-8", errors="replace")
                    symbols.append(CodeSymbol(
                        name=name,
                        symbol_type=sym_type,
                        start_line=start_l,
                        end_line=end_l,
                        signature=sig,
                        raw_code=raw,
                        language="go",
                    ))

        return symbols

    @classmethod
    def _parse_python(cls, root: Any, code_bytes: bytes) -> list[CodeSymbol]:
        symbols: list[CodeSymbol] = []

        def visit(node: Any, inside_class: bool = False) -> None:
            for child in node.children:
                actual_node = child
                # Unwrap decorated_definition
                if child.type == "decorated_definition":
                    defn = child.child_by_field_name("definition")
                    if defn:
                        actual_node = defn

                if actual_node.type in ("function_definition", "async_function_definition"):
                    name_node = actual_node.child_by_field_name("name")
                    if name_node:
                        name = name_node.text.decode("utf-8", errors="replace")
                        body = actual_node.child_by_field_name("body")
                        start_l, end_l = _calc_lines(child)
                        sig = _extract_sig_from_body(actual_node, body, code_bytes)
                        raw = child.text.decode("utf-8", errors="replace")
                        symbols.append(CodeSymbol(
                            name=name,
                            symbol_type="method" if inside_class else "function",
                            start_line=start_l,
                            end_line=end_l,
                            signature=sig,
                            raw_code=raw,
                            language="python",
                        ))
                    # Do not visit inner functions as class methods
                    continue

                elif actual_node.type == "class_definition":
                    name_node = actual_node.child_by_field_name("name")
                    if name_node:
                        name = name_node.text.decode("utf-8", errors="replace")
                        body = actual_node.child_by_field_name("body")
                        start_l, end_l = _calc_lines(child)
                        sig = _extract_sig_from_body(actual_node, body, code_bytes)
                        raw = child.text.decode("utf-8", errors="replace")
                        symbols.append(CodeSymbol(
                            name=name,
                            symbol_type="class",
                            start_line=start_l,
                            end_line=end_l,
                            signature=sig,
                            raw_code=raw,
                            language="python",
                        ))
                        if body:
                            visit(body, inside_class=True)
                    continue

                # Recurse for blocks or expression statements if needed
                if child.type not in ("function_definition", "class_definition"):
                    visit(child, inside_class=inside_class)

        visit(root, inside_class=False)
        return symbols

    @classmethod
    def _parse_typescript(cls, root: Any, code_bytes: bytes, lang_name: str) -> list[CodeSymbol]:
        symbols: list[CodeSymbol] = []

        def handle_node(node: Any, parent_export: Optional[Any] = None) -> None:
            container = parent_export if parent_export is not None else node

            if node.type == "export_statement":
                for sub in node.children:
                    if sub.type != "export":
                        handle_node(sub, parent_export=node)
                return

            if node.type == "function_declaration":
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = name_node.text.decode("utf-8", errors="replace")
                    body = node.child_by_field_name("body")
                    start_l, end_l = _calc_lines(container)
                    sig = _extract_sig_from_body(node, body, code_bytes)
                    raw = container.text.decode("utf-8", errors="replace")
                    symbols.append(CodeSymbol(
                        name=name,
                        symbol_type="function",
                        start_line=start_l,
                        end_line=end_l,
                        signature=sig,
                        raw_code=raw,
                        language="typescript",
                    ))

            elif node.type == "lexical_declaration":
                for decl in node.children:
                    if decl.type == "variable_declarator":
                        name_node = decl.child_by_field_name("name")
                        val_node = decl.child_by_field_name("value")
                        if name_node and val_node and val_node.type in ("arrow_function", "function_expression"):
                            name = name_node.text.decode("utf-8", errors="replace")
                            body = val_node.child_by_field_name("body")
                            start_l, end_l = _calc_lines(container)
                            sig = _extract_sig_from_body(container, body, code_bytes)
                            raw = container.text.decode("utf-8", errors="replace")
                            symbols.append(CodeSymbol(
                                name=name,
                                symbol_type="function",
                                start_line=start_l,
                                end_line=end_l,
                                signature=sig,
                                raw_code=raw,
                                language="typescript",
                            ))

            elif node.type == "class_declaration":
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = name_node.text.decode("utf-8", errors="replace")
                    body = node.child_by_field_name("body")
                    start_l, end_l = _calc_lines(container)
                    sig = _extract_sig_from_body(node, body, code_bytes)
                    raw = container.text.decode("utf-8", errors="replace")
                    symbols.append(CodeSymbol(
                        name=name,
                        symbol_type="class",
                        start_line=start_l,
                        end_line=end_l,
                        signature=sig,
                        raw_code=raw,
                        language="typescript",
                    ))
                    if body:
                        for m in body.children:
                            if m.type == "method_definition":
                                m_name_node = m.child_by_field_name("name")
                                if m_name_node:
                                    m_name = m_name_node.text.decode("utf-8", errors="replace")
                                    m_body = m.child_by_field_name("body")
                                    m_start, m_end = _calc_lines(m)
                                    m_sig = _extract_sig_from_body(m, m_body, code_bytes)
                                    m_raw = m.text.decode("utf-8", errors="replace")
                                    symbols.append(CodeSymbol(
                                        name=m_name,
                                        symbol_type="method",
                                        start_line=m_start,
                                        end_line=m_end,
                                        signature=m_sig,
                                        raw_code=m_raw,
                                        language="typescript",
                                    ))

            elif node.type == "interface_declaration":
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = name_node.text.decode("utf-8", errors="replace")
                    body = node.child_by_field_name("body")
                    start_l, end_l = _calc_lines(container)
                    sig = _extract_sig_from_body(node, body, code_bytes)
                    raw = container.text.decode("utf-8", errors="replace")
                    symbols.append(CodeSymbol(
                        name=name,
                        symbol_type="interface",
                        start_line=start_l,
                        end_line=end_l,
                        signature=sig,
                        raw_code=raw,
                        language="typescript",
                    ))

        for child in root.children:
            handle_node(child)

        return symbols

    @classmethod
    def _regex_fallback(cls, code: str, language: str) -> list[CodeSymbol]:
        """Line and regex-based fallback extractor when tree-sitter is unavailable or fails."""
        lines = code.splitlines()
        symbols: list[CodeSymbol] = []
        n_lines = len(lines)

        re_fn = re.compile(r"^\s*(?:pub\s+)?(?:async\s+)?(?:def|fn|func|function)\s+(?:\([^)]*\)\s+)?([A-Za-z_][A-Za-z0-9_]*)")
        re_arrow = re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_][A-Za-z0-9_]*)\s*=>")
        re_class = re.compile(r"^\s*(?:pub\s+)?(?:export\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)")
        re_struct = re.compile(r"^\s*(?:pub\s+)?(?:type\s+([A-Za-z_][A-Za-z0-9_]*)\s+struct|struct\s+([A-Za-z_][A-Za-z0-9_]*))")
        re_interface = re.compile(r"^\s*(?:pub\s+)?(?:export\s+)?(?:type\s+([A-Za-z_][A-Za-z0-9_]*)\s+interface|interface\s+([A-Za-z_][A-Za-z0-9_]*))")

        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith(("//", "#", "/*", "*")):
                continue

            name = None
            sym_type = None

            m_struct = re_struct.search(line)
            if m_struct:
                name = m_struct.group(1) or m_struct.group(2)
                sym_type = "struct"
            else:
                m_interface = re_interface.search(line)
                if m_interface:
                    name = m_interface.group(1) or m_interface.group(2)
                    sym_type = "interface"
                else:
                    m_class = re_class.search(line)
                    if m_class:
                        name = m_class.group(1)
                        sym_type = "class"
                    else:
                        m_fn = re_fn.search(line)
                        if m_fn:
                            name = m_fn.group(1)
                            # In Go, receiver before name means method
                            if "func (" in line or (language == "python" and (len(line) - len(line.lstrip())) > 0):
                                sym_type = "method"
                            else:
                                sym_type = "function"
                        else:
                            m_arrow = re_arrow.search(line)
                            if m_arrow:
                                name = m_arrow.group(1)
                                sym_type = "function"

            if name and sym_type:
                start_l = i + 1
                # Find end line by brace matching or indentation
                end_l = start_l
                brace_count = 0
                has_brace = False
                for j in range(i, n_lines):
                    l_text = lines[j]
                    for ch in l_text:
                        if ch == "{":
                            brace_count += 1
                            has_brace = True
                        elif ch == "}":
                            brace_count -= 1
                    if has_brace and brace_count <= 0:
                        end_l = j + 1
                        break
                if not has_brace:
                    # Line or indentation based
                    curr_indent = len(line) - len(line.lstrip())
                    for j in range(i + 1, n_lines):
                        next_line = lines[j]
                        if not next_line.strip():
                            continue
                        next_indent = len(next_line) - len(next_line.lstrip())
                        if next_indent <= curr_indent:
                            end_l = j
                            break
                    else:
                        end_l = n_lines

                sig = line.strip().rstrip(":{").strip()
                raw = "\n".join(lines[start_l - 1:end_l])
                symbols.append(CodeSymbol(
                    name=name,
                    symbol_type=sym_type,
                    start_line=start_l,
                    end_line=end_l,
                    signature=sig,
                    raw_code=raw,
                    language=language,
                ))

        return symbols
