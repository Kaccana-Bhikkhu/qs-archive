"""
New Tab Remote Extension for Python-Markdown
=====================================

Modify the behavior of Links in Python-Markdown to open a in a new
window. This changes the HTML output to add target="_blank" to all
generated links to remote resources.

A slightly modified version of the New Tab Extension
"""

from markdown import Extension
from markdown.inlinepatterns import \
    LinkInlineProcessor, ReferenceInlineProcessor, AutolinkInlineProcessor, AutomailInlineProcessor, \
    ShortReferenceInlineProcessor, \
    LINK_RE, REFERENCE_RE, AUTOLINK_RE, AUTOMAIL_RE

from urllib.parse import urlparse

class NewTabMixin(object):
    def handleMatch(self, m, data):
        el, start, end = super(NewTabMixin, self).handleMatch(m, data)
        if el is not None:
            link = el.get('href')
            if link:
                parsed = urlparse(link)
                if parsed.netloc or parsed.path.endswith(".pdf"):
                    el.set('target', '_blank')
        return el, start, end


class NewTabLinkProcessor(NewTabMixin, LinkInlineProcessor):
    pass


class NewTabReferenceProcessor(NewTabMixin, ReferenceInlineProcessor):
    pass


class NewTabAutolinkProcessor(NewTabMixin, AutolinkInlineProcessor):
    pass


class NewTabAutomailProcessor(NewTabMixin, AutomailInlineProcessor):
    pass


class NewTabShortReferenceProcessor(NewTabMixin, ShortReferenceInlineProcessor):
    pass


class NewTabRemoteExtension(Extension):
    """Modifies HTML output to open links in a new tab."""

    def extendMarkdown(self, md):
        md.inlinePatterns.register(NewTabLinkProcessor(LINK_RE, md), 'link', 160)
        md.inlinePatterns.register(NewTabReferenceProcessor(REFERENCE_RE, md), 'reference', 170)
        md.inlinePatterns.register(NewTabShortReferenceProcessor(REFERENCE_RE, md), 'short_reference', 130)
        md.inlinePatterns.register(NewTabAutolinkProcessor(AUTOLINK_RE, md), 'autolink', 120)
        md.inlinePatterns.register(NewTabAutomailProcessor(AUTOMAIL_RE, md), 'automail', 110)


def makeExtension(**kwargs):
    return NewTabRemoteExtension(**kwargs)
