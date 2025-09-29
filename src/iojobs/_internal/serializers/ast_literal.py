# ruff: noqa: ANN401
# pyright: reportExplicitAny=false


import ast
from typing import Any

from iojobs._internal.serializers.abc import JobsSerializer


class AstLiteralSerializer(JobsSerializer):
    def dumpb(self, value: Any) -> bytes:
        return repr(value).encode(encoding="utf-8")

    def loadb(self, value: bytes) -> Any:
        return ast.literal_eval(value.decode(encoding="utf-8"))
