import json
from timeit import timeit

data = {
    "users": [
        {"id": i, "name": f"User {i}", "email": f"user{i}@example.com"} for i in range(1000)
    ]
}

# Standard json
def test_standard_json():
    return timeit('json.dumps(data)', 'from __main__ import data,json', number=100)

# ujson (faster alternative)
def test_ujson():
    try:
        import ujson
        return timeit('ujson.dumps(data)', 'from __main__ import data,ujson', number=100)
    except ImportError:
        return "ujson not installed"

# orjson (high-performance)
def test_orjson():
    try:
        import orjson
        return timeit('orjson.dumps(data)', 'from __main__ import data,orjson', number=100)
    except ImportError:
        return "orjson not installed"


def main():
    print("Standard json:", test_standard_json())
    print("ujson:", test_ujson())
    print("orjson:", test_orjson())

if __name__ == "__main__":
    main()