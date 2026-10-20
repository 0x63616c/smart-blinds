"""Small lossless-atom reader/writer for the KiCad S-expressions used by our tools."""
from __future__ import annotations

import json
import re


class Atom(str):
    """An unquoted KiCad token, distinct from a quoted string."""


def parse(source: str) -> list:
    tokens = re.finditer(r'\s*(\(|\)|"(?:\\.|[^"\\])*"|[^\s()"]+)', source)
    stack = [[]]
    end = 0
    for match in tokens:
        if source[end:match.start()].strip():
            raise ValueError("Unsupported S-expression syntax")
        end = match.end()
        token = match[1]
        if token == "(":
            node = []
            stack[-1].append(node)
            stack.append(node)
        elif token == ")":
            if len(stack) == 1:
                raise ValueError("Unexpected closing parenthesis")
            stack.pop()
        else:
            stack[-1].append(json.loads(token) if token.startswith('"') else Atom(token))
    if source[end:].strip() or len(stack) != 1 or len(stack[0]) != 1:
        raise ValueError("Incomplete S-expression")
    return stack[0][0]


def dumps(value, depth=0) -> str:
    if isinstance(value, list):
        parts = [dumps(child, depth + 1) for child in value]
        if any(isinstance(child, list) for child in value):
            separator = "\n" + "  " * (depth + 1)
            return "(" + separator.join(parts) + ")"
        return "(" + " ".join(parts) + ")"
    if isinstance(value, Atom):
        return value
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def node(name, *values):
    return [Atom(name), *values]


def children(parent, tag):
    return [child for child in parent if isinstance(child, list) and child and child[0] == tag]


def one(parent, tag):
    matches = children(parent, tag)
    if len(matches) != 1:
        raise ValueError(f"Expected one {tag}, found {len(matches)}")
    return matches[0]


def walk(parent, tag):
    for child in parent:
        if isinstance(child, list):
            if child and child[0] == tag:
                yield child
            yield from walk(child, tag)
