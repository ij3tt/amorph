"""
The explanations: every «?» names a topic of helptext, opens it in a popup
whose link opens «Справка» at it, F1 opens the topic of the screen shown,
the page of «Справка» has every topic, and the columns of the tables say
what they show.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextDocument

from amorph_gui import helptext
from amorph_gui import strings as S
from amorph_gui.compare_screen import COLUMNS
from amorph_gui.main_window import COMPARE, DATA, HELP, RESULTS, RUNS
from amorph_gui.widgets import FigureView, HelpButton


def test_every_topic_is_on_the_page_once(qapp):
    keys = [key for _, topics in helptext.SECTIONS for key in topics]
    assert sorted(keys) == sorted(helptext.TOPICS)
    assert len(keys) == len(set(keys))
    for key, (title, short, body) in helptext.TOPICS.items():
        assert title and short and body, key
        # Rich text that Qt reads, with some words in it
        document = QTextDocument()
        document.setHtml(body)
        assert len(document.toPlainText()) > 40, key
    for key in helptext.SCREEN_TOPICS + list(
            helptext.FIGURE_TOPICS.values()):
        assert key in helptext.TOPICS


def buttons(screen):
    return screen.findChildren(HelpButton)


def test_the_screens_have_their_explanations(window, qtbot, archives):
    for screen in (window.data_screen, window.runs_screen,
                   window.compare_screen):
        assert buttons(screen), screen.title
    window.open_archive(archives["seed5"])
    qtbot.waitUntil(lambda: window.results_screen.archive
                    == archives["seed5"], timeout=20000)
    results = window.results_screen
    # The figures of every tab, each with its «?»
    for i in range(results.tabs.count()):
        results.tabs.setCurrentIndex(i)
        assert results.tabs.tabToolTip(i)
    views = results.findChildren(FigureView)
    assert views
    for view in views:
        assert view.help_button.topic == helptext.FIGURE_TOPICS[view.name]
    for screen in window.screens:
        for button in buttons(screen):
            assert button.topic in helptext.TOPICS
            assert helptext.short(button.topic) in button.toolTip()


def test_a_question_mark_opens_its_topic(window, qtbot):
    window.show_screen(RUNS)
    button = [b for b in buttons(window.runs_screen)
              if b.topic == "estimate"][0]
    popup = button.show_popup()
    assert popup.isVisible()
    assert popup.width() == 440
    assert "20%" in popup.text.text()
    # Its link opens «Справка» at the topic
    popup.open_help()
    assert window.stack.currentIndex() == HELP
    assert window.help_screen.topic == "estimate"


def test_f1_opens_the_topic_of_the_screen(window):
    for index, topic in zip((DATA, RUNS, RESULTS, COMPARE),
                            helptext.SCREEN_TOPICS):
        window.show_screen(index)
        window.show_help()
        assert window.stack.currentIndex() == HELP
        assert window.help_screen.topic == topic
    # On «Справка» itself it stays where it is
    window.show_help()
    assert window.help_screen.topic == helptext.SCREEN_TOPICS[-1]


def test_the_help_page_has_every_topic(window):
    text = window.help_screen.browser.toHtml()
    for key, (title, _, _) in helptext.TOPICS.items():
        assert 'name="{0}"'.format(key) in text
    plain = window.help_screen.browser.toPlainText()
    assert S.HELP_CONTENTS in plain
    for section, _ in helptext.SECTIONS:
        assert section in plain
    assert window.nav.item(HELP).text().endswith(S.SCREEN_HELP)


def test_the_columns_say_what_they_show(window):
    model = window.compare_screen.model
    for i in range(len(COLUMNS)):
        assert model.headerData(i, Qt.Horizontal, Qt.ToolTipRole)
    table = window.runs_screen.table
    for i in range(table.columnCount()):
        assert S.RUNS_COLUMN_TIPS[i] in table.horizontalHeaderItem(
            i).toolTip()
    for key, button in window.runs_screen.layer_buttons.items():
        assert S.LAYER_TIPS[key] in button.toolTip()
    for key, button in window.runs_screen.view_buttons.items():
        assert S.VIEW_TIPS[key] in button.toolTip()
    # Rich text, which Qt wraps, unlike plain text however long
    assert window.runs_screen.stop_button.toolTip().startswith("<p>")
