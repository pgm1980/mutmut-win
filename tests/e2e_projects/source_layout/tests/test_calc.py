from pkglib.calc import double


def test_double() -> None:
    assert double(3) == 6
    assert double(0) == 0
