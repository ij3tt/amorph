"""
The screen «Справка»: every topic of helptext on one page, by sections,
after their contents. A «?» (widgets.HelpButton) and F1 open it at a topic
(show_topic).
"""

import html

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QHBoxLayout, QTextBrowser

from amorph_gui import helptext
from amorph_gui import strings as S
from amorph_gui import theme
from amorph_gui.widgets import Screen, card

# The widest the text gets, in pixels: long lines are hard to read
MAX_WIDTH = 920

STYLE = """
h2 {{ color: {ACCENT_DARK}; font-size: 14pt; margin-top: 22px; }}
h3 {{ font-size: 11.5pt; margin-top: 16px; margin-bottom: 4px; }}
p, li {{ line-height: 135%; }}
a {{ color: {ACCENT}; text-decoration: none; }}
tt {{ font-family: {MONO}; }}
.contents {{ color: {MUTED}; }}
""".format(ACCENT_DARK=theme.ACCENT_DARK, ACCENT=theme.ACCENT,
           MUTED=theme.MUTED, MONO=theme.css_families(theme.MONO))


def page():
    """
    The page: the contents, then each section with its topics, each topic
    with an anchor of its key.
    """
    contents = []
    sections = []
    for section, topics in helptext.SECTIONS:
        links = ", ".join('<a href="#{0}">{1}</a>'.format(
            key, html.escape(helptext.TOPICS[key][0])) for key in topics)
        contents.append("<p><b>{0}</b>: {1}</p>".format(
            html.escape(section), links))
        sections.append("<h2>{0}</h2>".format(html.escape(section)))
        for key in topics:
            title, _, body = helptext.TOPICS[key]
            sections.append('<h3><a name="{0}"></a>{1}</h3>{2}'.format(
                key, html.escape(title), body))
    return "<h2>{0}</h2>{1}{2}".format(S.HELP_CONTENTS,
                                       "".join(contents), "".join(sections))


class HelpScreen(Screen):
    """
    topic: the topic shown last (show_topic).
    """

    def __init__(self, parent=None):
        super().__init__(S.SCREEN_HELP, parent)
        self.topic = None
        self.set_header("", S.HELP_HEADER)
        self.archive_button.hide()
        frame, layout = card(margins=2)
        frame.setMaximumWidth(MAX_WIDTH)
        self.browser = QTextBrowser()
        self.browser.setObjectName("help")
        self.browser.document().setDefaultStyleSheet(STYLE)
        self.browser.document().setDocumentMargin(20)
        self.browser.setHtml(page())
        layout.addWidget(self.browser)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(frame, 100)
        row.addStretch(1)
        self.body.addLayout(row, 1)

    def show_topic(self, topic):
        """
        Scroll to topic, once the page has its size.
        """
        self.topic = topic
        QTimer.singleShot(0, self.browser,
                          lambda: self.browser.scrollToAnchor(topic))
