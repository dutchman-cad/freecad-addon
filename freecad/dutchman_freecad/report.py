# SPDX-License-Identifier: Apache-2.0
"""Stable, GUI-independent presentation of dutchman.convert/1 reports."""

import html
import re
from urllib.parse import urlparse

DISCORD = "https://discord.gg/yTcseBEdeu"
ISSUES = "https://github.com/dutchman-cad/freecad-addon/issues"
MAX_NOTES = 3
MAX_NOTE_CHARS = 200


def mode_label(report):
    mode = str(report.get("mode", "")).lower().replace("-", "_")
    if "partial" in mode:
        return "partial"
    if "geometry" in mode:
        return "geometry only"
    history = report.get("history") or {}
    total = history.get("total", 0) or 0
    rebuilt = history.get("rebuilt", 0) or 0
    mapped = history.get("mapped", 0) or 0
    if total and rebuilt >= total:
        return "full history"
    if total and (rebuilt or mapped):
        return "partial"
    return "full history" if "history" in mode and "full" in mode else "geometry only"


def lines(report):
    history = report.get("history") or {}
    verification = report.get("verification") or {}
    result = [("Dutchman: ok — " + mode_label(report)) if report.get("ok") else "Dutchman: failed",
              "History: mapped {} / rebuilt {} / total {}".format(
                  history.get("mapped", 0), history.get("rebuilt", 0), history.get("total", 0)),
              "Verification: {} — {}".format(verification.get("status", "unknown"),
                                              verification.get("reason") or "No reason supplied")]
    for loss in report.get("losses") or []:
        result.append("{}: {}".format((loss.get("code") or "info"),
                                     loss.get("detail", loss.get("message", ""))))
    return result


def loss_line(loss):
    return "{}: {}".format(loss.get("code") or "info", loss.get("detail", loss.get("message", "")))


def docs_link(loss):
    value = loss.get("docs_url") or loss.get("docs_link") or loss.get("docs") or loss.get("url")
    if isinstance(value, str) and urlparse(value).scheme in ("https", "http"):
        return value
    return None


def error_message(report):
    error = report.get("error") or {}
    if isinstance(error, dict):
        return str(error.get("message") or
                   "Import failed. Check the Dutchman executable and source file.")
    return str(error)


_URL = re.compile(r"https?://[^\s<>\"']+")


def _linkify(text):
    """Escape text, then turn http(s) URLs into links (the URL is escaped too)."""
    escaped = html.escape(text)
    return _URL.sub(lambda m: '<a href="{0}">{0}</a>'.format(m.group(0).rstrip(".,;)")) +
                    m.group(0)[len(m.group(0).rstrip(".,;)")):], escaped)


def _help_block(setup_problem):
    if setup_problem:
        return ("<h3>Set up Dutchman</h3>"
                "<p>Open <b>Edit &gt; Preferences &gt; Dutchman</b> to say where Dutchman is or to turn on "
                "its download, then open the file again.</p>")
    return ('<h3>Is there a problem? Is something missing?</h3>'
            '<p><a href="{}">Join our Discord</a>, '
            'then DM Dutchy for private help. '
            'Review files and reports before sharing them.</p>'
            '<p>You can also <a href="{}">open a GitHub issue</a>. '
            'GitHub issues are public.</p>').format(DISCORD, ISSUES)


def as_html(report):
    """Headline first, help next, details last: the narrow dock must not bury either."""
    ok = report.get("ok")
    setup_problem = bool(report.get("setup_problem"))
    history = report.get("history") or {}
    verification = report.get("verification") or {}
    result = []
    if report.get("source_name"):
        result.append("<h3>" + html.escape(str(report["source_name"])) + "</h3>")
    if not ok:
        result.append('<p><b style="color:#e06c6c">Import failed</b></p><p>'
                      + _linkify(error_message(report)) + "</p>")
    else:
        label = mode_label(report)
        headline = {"full history": "Imported with full feature history",
                    "partial": "Imported with partial feature history",
                    "geometry only": "Imported as geometry only"}[label]
        colour = "#7bc67b" if label == "full history" else "#e0b050"
        result.append('<p><b style="color:{}">{}</b></p>'.format(colour, headline))
        if label == "geometry only":
            result.append("<p>The shapes are in your document, but without editable feature history.</p>")
        if history.get("total"):
            result.append("<p>History: {} of {} features rebuilt ({} mapped).</p>".format(
                history.get("rebuilt", 0), history["total"], history.get("mapped", 0)))
        if verification.get("status") or verification.get("reason"):
            result.append("<p>Verification: {}{}</p>".format(
                html.escape(str(verification.get("status", "unknown"))),
                " — " + html.escape(str(verification["reason"])) if verification.get("reason") else ""))
        if report.get("saved_copy"):
            result.append("<p>Copy saved to {}</p>".format(html.escape(str(report["saved_copy"]))))
    result.append(_help_block(setup_problem))
    losses = report.get("losses") or []
    if losses:
        result.append("<h3>Notes ({})</h3>".format(len(losses)))
        for loss in losses[:MAX_NOTES]:
            link = docs_link(loss)
            text = loss_line(loss)
            if len(text) > MAX_NOTE_CHARS:
                text = text[:MAX_NOTE_CHARS].rstrip() + "…"
            result.append("<p><small>" + html.escape(text) +
                          (' <a href="{}">Documentation</a>'.format(html.escape(link, quote=True))
                           if link else "") + "</small></p>")
        if len(losses) > MAX_NOTES:
            result.append("<p><small>{} more notes are in the full report (Dutchman convert --json).</small></p>"
                          .format(len(losses) - MAX_NOTES))
    return "".join(result)
