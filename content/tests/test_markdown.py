from __future__ import annotations

from django.utils.safestring import SafeString

from content.markdown import render_markdown


def test_markdown_renders_allowed_features() -> None:
    html = render_markdown(
        "# Heading\n\n"
        "- One\n"
        "- Two\n\n"
        "[Link](/pages/info/)\n\n"
        "![Map](/media/map.png)\n\n"
        "```\ncode\n```\n\n"
        "| A | B |\n|---|---|\n| 1 | 2 |"
    )

    assert isinstance(html, SafeString)
    assert "<h1>Heading</h1>" in html
    assert "<li>One</li>" in html
    assert '<a href="/pages/info/">Link</a>' in html
    assert '<img alt="Map" src="/media/map.png">' in html
    assert "<code>code" in html
    assert "<table>" in html
    assert "<th>A</th>" in html
    assert "<td>1</td>" in html


def test_markdown_neutralizes_raw_html() -> None:
    html = render_markdown('<script>alert("x")</script><p onclick="bad()">Hello</p>')

    assert "<script" not in html
    assert "<p onclick" not in html
    assert "&lt;script&gt;" in html


def test_raw_html_tables_are_not_trusted_but_pipe_tables_render() -> None:
    html = render_markdown("<table><tr><td>Raw</td></tr></table>")
    pipe_table_html = render_markdown("| A |\n|---|\n| Safe |")

    assert "<table><tr><td>Raw" not in html
    assert "&lt;table&gt;" in html
    assert "<table>" in pipe_table_html
    assert "<td>Safe</td>" in pipe_table_html


def test_markdown_blocks_unsafe_links_and_images() -> None:
    html = render_markdown(
        "[Bad](javascript:alert(1))\n\n"
        "![Bad](data:image/png;base64,abc)\n\n"
        "![Remote](http://example.com/image.png)\n\n"
        "![Good](https://example.com/image.png)"
    )

    assert "javascript:" not in html
    assert "data:image" not in html
    assert "http://example.com/image.png" not in html
    assert "https://example.com/image.png" in html
