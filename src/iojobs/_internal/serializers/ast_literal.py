import ast
from typing import TypeAlias, cast

from iojobs._internal.serializers.abc import JobsSerializer

AstLiteralTypes: TypeAlias = (
    None
    | bool
    | int
    | float
    | str
    | bytes
    | set["AstLiteralTypes"]
    | list["AstLiteralTypes"]
    | tuple["AstLiteralTypes"]
    | dict[str, "AstLiteralTypes"]
)


class AstLiteralSerializer(JobsSerializer):
    def dumpb(self, value: AstLiteralTypes) -> bytes:
        return repr(value).encode(encoding="utf-8")

    def loadb(self, value: bytes) -> AstLiteralTypes:
        return cast(
            "AstLiteralTypes",
            ast.literal_eval(value.decode(encoding="utf-8")),
        )
