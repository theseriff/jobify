from timeit import timeit

from iojobs.serializers import (
    JobsSerializer,
    JSONSerializer,
    SerializableTypes,
    UnsafePickleSerializer,
)

big_serializable_data: dict[str, SerializableTypes] = {
    # Simple types
    "none_value": None,
    "boolean_true": True,
    "boolean_false": False,
    "positive_int": 42,
    "negative_int": -15,
    "zero": 0,
    "positive_float": 3.14159,
    "negative_float": -2.71828,
    "simple_string": "Hello, World!",
    "empty_string": "",
    "unicode_string": "Привет, мир! 🌍",
    "binary_data": b"binary_data_bytes",
    "empty_bytes": b"",
    # Collections
    "simple_set": {1, 2, 3, 4, 5},
    "string_set": {"apple", "banana", "cherry"},
    "mixed_set": {1, "text", 3.14},
    "empty_set": set(),
    "simple_list": [1, 2, 3, 4, 5],
    "mixed_list": [None, True, 42, 3.14, "text", b"data"],
    "nested_list": [[1, 2], [3, 4], [5, 6]],
    "deep_list": [1, [2, [3, [4, [5]]]]],
    "empty_list": [],
    "simple_tuple": (1, "two", 3.0, None),
    "boolean_tuple": (True, False),
    "bytes_tuple": (b"bytes1", b"bytes2"),
    "single_tuple": ("single",),
    "empty_tuple": (),
    # Dictionaries
    "simple_dict": {"name": "Alice", "age": 30, "is_active": True},
    "nested_dict": {
        "user": {
            "id": 12345,
            "profile": {
                "first_name": "John",
                "last_name": "Doe",
                "preferences": {"theme": "dark", "language": "en"},
            },
        },
    },
    "mixed_dict": {
        "int_value": 42,
        "float_value": 3.14,
        "string_value": "hello",
        "none_value": None,
        "bool_value": False,
        "bytes_value": b"data",
    },
    "empty_dict": {},
    # Complex nested structures
    "complex_structure": {
        "users": [
            {
                "id": 1,
                "name": "Alice",
                "tags": {"admin", "moderator"},
                "scores": (95, 87, 92),
                "metadata": {"created_at": "2023-01-01", "is_verified": True},
            },
            {
                "id": 2,
                "name": "Bob",
                "tags": {"user"},
                "scores": (78, 85, 80),
                "metadata": {"created_at": "2023-01-02", "is_verified": False},
            },
        ],
        "system_info": {
            "version": 2.1,
            "features": {"auth", "logging", "api"},
            "config": {"debug": True, "max_connections": 100, "timeout": 30.5},
        },
    },
    # Matrices and multidimensional data
    "matrix": [[1, 2, 3], [4, 5, 6], [7, 8, 9]],
    "coordinates": [
        (40.7128, -74.0060),  # NY
        (51.5074, -0.1278),  # London
        (35.6762, 139.6503),  # Tokyo
    ],
    # Edge cases
    "edge_cases": {
        "empty_structures": {
            "empty_list": [],
            "empty_dict": {},
            "empty_set": set(),
            "empty_tuple": (),
            "empty_string": "",
            "empty_bytes": b"",
        },
        "single_items": {
            "single_list": [None],
            "single_dict": {"key": "value"},
            "single_set": {42},
            "single_tuple": ("only",),
        },
        "deep_nesting": {
            "level1": {
                "level2": [{"level3": {"level4": {"level5": "deep_value"}}}],
            },
        },
    },
    # Data with different type combinations
    "mixed_collections": {
        "list_of_sets": [{1, 2}, {3, 4}, {5, 6}],
        "set_of_tuples": {("a", 1), ("b", 2), ("c", 3)},
        "tuple_of_lists": ([1, 2], [3, 4], [5, 6]),
        "dict_with_collections": {
            "list_key": [1, 2, 3],
            "set_key": {"x", "y", "z"},
            "tuple_key": (True, False, None),
        },
    },
    # Special values
    "special_numbers": {
        "large_int": 10**18,
        "small_int": -(10**18),
        "float_precision": 0.1 + 0.2,  # 0.30000000000000004
        "scientific": 1.23e-10,
    },
    # Unicode and special characters
    "unicode_data": {
        "emojis": "😀 🎉 🌟 📚 💻",
        "special_chars": "Line1\nLine2\tTabbed\\Backslash",
        "unicode_mix": "Hello 世界 🌍 Привет",
        "escape_chars": 'New\nLine\tTab"Quote\\Backslash',
    },
}


def serializer_case(serializer: JobsSerializer) -> None:
    encoded = serializer.dumpb(big_serializable_data)
    decoded = serializer.loadb(encoded)
    assert decoded == big_serializable_data


def serializers_measure() -> dict[str, dict[str, float]]:
    results: dict[str, float] = {}
    common_globs = {"serializer_case": serializer_case}
    stmt = "for _ in range(100): serializer_case(serializer)"
    for k, serializer in {
        "json": JSONSerializer(),
        "pickle": UnsafePickleSerializer(),
    }.items():
        globs = common_globs | {"serializer": serializer}
        results[k] = timeit(stmt, globals=globs, number=1000)
    results = dict(sorted(results.items(), key=lambda item: item[1]))
    return {"serializers": results}
