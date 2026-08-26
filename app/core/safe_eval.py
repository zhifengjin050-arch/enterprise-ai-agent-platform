"""Restricted expression evaluator for workflow conditions.

Only literals, names, comparisons, boolean/arithmetic ops, and a small
set of builtins are allowed. Attribute access to dunder names is rejected.
"""

from __future__ import annotations

import ast
import operator
from typing import Any, Dict, Mapping

_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARYOPS = {
    ast.Not: operator.not_,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}
_CMPOPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.In: lambda left, right: left in right,
    ast.NotIn: lambda left, right: left not in right,
}
_ALLOWED_CALLS = {
    "abs": abs,
    "len": len,
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "min": min,
    "max": max,
    "sum": sum,
    "any": any,
    "all": all,
}
_CONST_NAMES = {"True": True, "False": False, "None": None}


class UnsafeExpressionError(ValueError):
    """Raised when an expression uses a disallowed construct."""


def safe_eval(expression: str, names: Mapping[str, Any] | None = None) -> Any:
    """Evaluate a restricted Python expression against ``names``."""
    if not expression or not expression.strip():
        raise UnsafeExpressionError("empty expression")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise UnsafeExpressionError(f"invalid expression: {exc}") from exc
    return _eval_node(tree.body, dict(names or {}))


def _eval_node(node: ast.AST, names: Dict[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id in names:
            return names[node.id]
        if node.id in _CONST_NAMES:
            return _CONST_NAMES[node.id]
        raise UnsafeExpressionError(f"unknown name: {node.id}")
    if isinstance(node, ast.UnaryOp):
        op = _UNARYOPS.get(type(node.op))
        if op is None:
            raise UnsafeExpressionError("unsupported unary operator")
        return op(_eval_node(node.operand, names))
    if isinstance(node, ast.BinOp):
        op = _BINOPS.get(type(node.op))
        if op is None:
            raise UnsafeExpressionError("unsupported binary operator")
        return op(_eval_node(node.left, names), _eval_node(node.right, names))
    if isinstance(node, ast.BoolOp):
        values = [_eval_node(v, names) for v in node.values]
        if isinstance(node.op, ast.And):
            return all(values)
        if isinstance(node.op, ast.Or):
            return any(values)
        raise UnsafeExpressionError("unsupported boolean operator")
    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, names)
        for op_node, comparator in zip(node.ops, node.comparators):
            fn = _CMPOPS.get(type(op_node))
            if fn is None:
                raise UnsafeExpressionError("unsupported comparison")
            right = _eval_node(comparator, names)
            if not fn(left, right):
                return False
            left = right
        return True
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _ALLOWED_CALLS:
            raise UnsafeExpressionError("function call not allowed")
        if node.keywords:
            raise UnsafeExpressionError("keyword arguments not allowed")
        args = [_eval_node(a, names) for a in node.args]
        return _ALLOWED_CALLS[node.func.id](*args)
    if isinstance(node, ast.Attribute):
        if node.attr.startswith("_"):
            raise UnsafeExpressionError("private attribute access is not allowed")
        obj = _eval_node(node.value, names)
        if not hasattr(obj, node.attr):
            raise UnsafeExpressionError(f"unknown attribute: {node.attr}")
        return getattr(obj, node.attr)
    if isinstance(node, ast.Subscript):
        obj = _eval_node(node.value, names)
        key = _eval_node(node.slice, names)
        return obj[key]
    if isinstance(node, ast.List):
        return [_eval_node(elt, names) for elt in node.elts]
    if isinstance(node, ast.Tuple):
        return tuple(_eval_node(elt, names) for elt in node.elts)
    if isinstance(node, ast.Dict):
        return {
            _eval_node(k, names): _eval_node(v, names)
            for k, v in zip(node.keys, node.values)
            if k is not None
        }
    raise UnsafeExpressionError(f"unsupported syntax: {type(node).__name__}")
