from norm import normalize


def test_normalize_returns_list():
    result = normalize((1, 2))
    assert result == [1, 2]
    assert isinstance(result, list)


def test_normalize_copies():
    src = [1, 2]
    result = normalize(src)
    assert result == src
    assert result is not src
