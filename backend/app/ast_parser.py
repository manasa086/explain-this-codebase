import ast
from dataclasses import dataclass, field


def _name_of(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


class _CallCollector(ast.NodeVisitor):
    def __init__(self):
        self.calls: list[str] = []

    def visit_Call(self, node: ast.Call):
        name = _name_of(node.func)
        if name:
            self.calls.append(name)
        self.generic_visit(node)


@dataclass
class ParsedImport:
    module: str
    names: list[str]


@dataclass
class ParsedFunction:
    name: str
    qualname: str
    start_line: int
    end_line: int
    calls: list[str]


@dataclass
class ParsedClass:
    name: str
    bases: list[str]
    start_line: int
    end_line: int
    methods: list[str]


@dataclass
class ParsedFile:
    imports: list[ParsedImport] = field(default_factory=list)
    functions: list[ParsedFunction] = field(default_factory=list)
    classes: list[ParsedClass] = field(default_factory=list)


def _extract_function(node: ast.FunctionDef | ast.AsyncFunctionDef, qualname: str) -> ParsedFunction:
    collector = _CallCollector()
    for child in node.body:
        collector.visit(child)
    return ParsedFunction(
        name=node.name,
        qualname=qualname,
        start_line=node.lineno,
        end_line=getattr(node, "end_lineno", node.lineno),
        calls=collector.calls,
    )


def parse_source(source: str) -> ParsedFile:
    tree = ast.parse(source)
    parsed = ParsedFile()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                parsed.imports.append(ParsedImport(module=alias.name, names=[]))
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            # relative imports (level > 0) are skipped; resolving them needs
            # package-relative path math the graph builder doesn't do yet
            parsed.imports.append(
                ParsedImport(module=node.module or "", names=[a.name for a in node.names])
            )

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            parsed.functions.append(_extract_function(node, qualname=node.name))
        elif isinstance(node, ast.ClassDef):
            method_names = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    parsed.functions.append(
                        _extract_function(item, qualname=f"{node.name}.{item.name}")
                    )
                    method_names.append(item.name)
            parsed.classes.append(
                ParsedClass(
                    name=node.name,
                    bases=[b.id for b in node.bases if isinstance(b, ast.Name)],
                    start_line=node.lineno,
                    end_line=getattr(node, "end_lineno", node.lineno),
                    methods=method_names,
                )
            )

    return parsed


def parse_file(path) -> ParsedFile:
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()
    return parse_source(source)
