from pathlib import Path

from m_standard.tools.extract_ydb import extract_operators

RST = """\
==============
5. Language features
==============

The arithmetic operators are:

+-----------+----------------------------------------+
| Operator  | Description                            |
+===========+========================================+
| \\+       | binary operator for addition           |
+-----------+----------------------------------------+
| \\-       | binary operator for subtraction        |
+-----------+----------------------------------------+

Some prose.

The logical operators are:

+-----------+----------------------------------------+
| Operator  | Description                            |
+===========+========================================+
| '         | unary NOT operator                     |
+-----------+----------------------------------------+
| &         | binary AND operator                    |
+-----------+----------------------------------------+

The numeric relational operators are:

+-----------+----------------------------------------+
| Operator  | Description                            |
+===========+========================================+
| =         | numeric equality                       |
+-----------+----------------------------------------+
| >         | numeric greater-than                   |
+-----------+----------------------------------------+

The string relational operators are:

+-----------+----------------------------------------+
| Operator  | Description                            |
+===========+========================================+
| [         | string contains                        |
+-----------+----------------------------------------+
| ]]        | string follows                         |
+-----------+----------------------------------------+
"""


def test_extract_operators_finds_each_class(tmp_path: Path) -> None:
    src = tmp_path / "langfeat.rst"
    src.write_text(RST)
    ops = extract_operators(src)
    classes = {o.operator_class for o in ops}
    assert classes == {
        "arithmetic", "logical", "numeric-relational", "string-relational"
    }


def test_extract_operators_strips_rst_escapes(tmp_path: Path) -> None:
    src = tmp_path / "langfeat.rst"
    src.write_text(RST)
    by_sym = {(o.operator_class, o.symbol) for o in extract_operators(src)}
    assert ("arithmetic", "+") in by_sym
    assert ("arithmetic", "-") in by_sym
    assert ("logical", "'") in by_sym
    assert ("string-relational", "]]") in by_sym
