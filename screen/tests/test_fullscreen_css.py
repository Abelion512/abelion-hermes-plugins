"""Phone-landscape fullscreen hides the toolbar; nothing else does.
Static guard on the shipped CSS/JS wiring (pixels were checked separately in a
real browser): the hide rule must be scoped to fullscreen + landscape + touch,
so desktop, portrait and non-fullscreen layouts keep their controls."""
import re
from pathlib import Path

DIST = Path(__file__).parent.parent / "dashboard" / "dist"


def test_toolbar_hidden_only_in_fullscreen_landscape_touch():
    css = (DIST / "style.css").read_text()
    rules = re.findall(r"@media\s*([^{]+)\{([^{}]*\{[^{}]*\}[^{}]*)\}", css)
    hiding = [(m, b) for m, b in rules if "display: none" in b and "hermes-screen-toolbar" in b]
    assert len(hiding) == 1, hiding
    media, body = hiding[0]
    assert "orientation: landscape" in media and "pointer: coarse" in media
    assert ".hermes-screen-page--fs .hermes-screen-toolbar" in body
    # no unconditional rule hides the toolbar
    outside = re.sub(r"@media[^{]+\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", "", css)
    assert not re.search(r"hermes-screen-toolbar[^{]*\{[^}]*display:\s*none", outside)


def test_page_gets_fs_class_from_fullscreen_state():
    js = (DIST / "index.js").read_text()
    assert 'isFs ? " hermes-screen-page--fs" : ""' in js
