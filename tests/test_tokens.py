def test_build_qss_contains_bg_token():
    from bertytype.ui.tokens import build_qss, BG
    assert BG in build_qss("dark")


def test_build_qss_contains_accent_token():
    from bertytype.ui.tokens import build_qss, ACCENT
    assert ACCENT in build_qss("dark")


def test_build_qss_contains_border_token():
    from bertytype.ui.tokens import build_qss, BORDER
    assert BORDER in build_qss("dark")


def test_build_qss_contains_text_token():
    from bertytype.ui.tokens import build_qss, TEXT
    assert TEXT in build_qss("dark")


def test_build_qss_dark_returns_nonempty():
    from bertytype.ui.tokens import build_qss
    result = build_qss("dark")
    assert isinstance(result, str) and len(result) > 100


def test_build_qss_light_returns_nonempty():
    from bertytype.ui.tokens import build_qss
    result = build_qss("light")
    assert isinstance(result, str) and len(result) > 100


def test_build_qss_light_contains_light_bg():
    from bertytype.ui.tokens import build_qss
    result = build_qss("light")
    assert "#f5f5f5" in result  # light background token


def test_build_qss_dark_contains_dark_bg():
    from bertytype.ui.tokens import build_qss, BG
    result = build_qss("dark")
    assert BG in result


def test_build_qss_default_is_dark():
    from bertytype.ui.tokens import build_qss, BG
    assert BG in build_qss()


def test_both_palettes_have_same_keys():
    from bertytype.ui.tokens import _dark_palette, _light_palette
    assert set(_dark_palette().keys()) == set(_light_palette().keys())
