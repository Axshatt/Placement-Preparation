#!/usr/bin/env python3
"""
Build the static site in docs/ from the repository's markdown files.

No dependencies. Run:  python3 tools/build_site.py
Output is committed, so GitHub Pages can serve /docs directly.
"""

import html
import json
import os
import re
import shutil
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs")
TOOLS = os.path.join(ROOT, "tools")

SITE_TITLE = "Tier-3 to Top Tech"
SITE_NAME = "Placement Preparation Roadmap"
REPO_URL = "https://github.com/Axshatt/Placement-Preparation"


# Sidebar structure: (group label, [(source md path, nav label)])
NAV = [
    ("Start here", [
        ("README.md", "Home"),
        ("START-HERE.md", "Start Here"),
    ]),
    ("The 4-year roadmap", [
        ("roadmap/README.md", "Overview"),
        ("roadmap/year-1.md", "Year 1 — Build the base"),
        ("roadmap/year-2.md", "Year 2 — Go deep"),
        ("roadmap/year-3.md", "Year 3 — Get proof"),
        ("roadmap/year-4.md", "Year 4 — Convert"),
        ("roadmap/late-start.md", "Started late?"),
    ]),
    ("Career tracks", [
        ("tracks/README.md", "Choose a track"),
        ("tracks/frontend.md", "Frontend"),
        ("tracks/backend.md", "Backend"),
        ("tracks/full-stack.md", "Full Stack"),
        ("tracks/qa-sdet.md", "QA / SDET"),
        ("tracks/devops-cloud.md", "DevOps / Cloud"),
        ("tracks/data-ai-ml.md", "Data / AI / ML"),
        ("tracks/mobile.md", "Mobile"),
        ("tracks/non-coding-tech-roles.md", "Non-coding tech"),
    ]),
    ("Core skills", [
        ("core/dsa.md", "DSA"),
        ("core/aptitude-and-maths.md", "Aptitude & Maths"),
        ("core/cs-fundamentals.md", "CS Fundamentals"),
        ("core/system-design.md", "System Design"),
        ("core/git-and-linux.md", "Git & Linux"),
    ]),
    ("Getting hired", [
        ("placements/company-tiers.md", "Company tiers"),
        ("placements/off-campus-strategy.md", "Off-campus strategy"),
        ("placements/resume.md", "Resume"),
        ("placements/portfolio-and-github.md", "GitHub & portfolio"),
        ("placements/linkedin-and-networking.md", "LinkedIn & networking"),
        ("placements/internships.md", "Internships"),
        ("placements/interview-playbook.md", "Interview playbook"),
    ]),
    ("Build & practice", [
        ("projects/README.md", "Project ideas"),
        ("resources/free-resources.md", "Free resources"),
        ("resources/practice-platforms.md", "Practice platforms"),
    ]),
    ("Templates", [
        ("templates/90-day-plan.md", "90-day plan"),
        ("templates/weekly-tracker.md", "Weekly tracker"),
        ("templates/resume-template.md", "Resume template"),
    ]),
    ("Popular guides", [
        ("guides/tier-3-college-placement.md", "Tier-3 college placement"),
        ("guides/btech-placement-preparation.md", "B.Tech placement prep"),
        ("guides/software-engineer-roadmap-india.md", "SDE roadmap (India)"),
        ("guides/dsa-roadmap-for-placement.md", "DSA roadmap"),
        ("guides/off-campus-placement-guide.md", "Off-campus placement"),
    ]),
]


# Directories that are linked as `dir/` but have no README.md — build an index for them.
SECTIONS = {
    "core": ("Core skills",
             "The five things every track needs underneath it. None of these are optional.",
             "Core skills"),
    "placements": ("Getting hired",
                   "Who to target, what to send them, and how to convert the interview once you're in the room.",
                   "Getting hired"),
    "resources": ("Resources",
                  "Everything you need is free. These are the pages that prove it.",
                  "Build & practice"),
    "guides": ("Popular guides",
               "The questions students search for most, answered in full and linked "
               "into the detailed roadmaps.",
               "Popular guides"),
    "templates": ("Templates",
                  "Copy these into your fork and fill them in. Planning is 15 minutes a week, not a hobby.",
                  "Templates"),
}

ALERTS = {
    "NOTE":      ("note", "Note"),
    "TIP":       ("tip", "Tip"),
    "IMPORTANT": ("important", "Important"),
    "WARNING":   ("warning", "Warning"),
    "CAUTION":   ("caution", "Caution"),
}

RAW_HTML_RE = re.compile(r"^\s*</?(div|details|summary|br|img|p|span|kbd|sup|sub)\b", re.I)


# ─────────────────────────────────────────────────────────── helpers ──

# The markdown hardcodes colours picked for GitHub's dark theme. They clash
# with this site's palette, so remap them on the way out: deep tinted fills
# from our own ink range, strokes from our accent set. GitHub keeps its own.
MERMAID_PALETTE = {
    "#065f46": "#0E2A21", "#10b981": "#34D399",   # green
    "#1e40af": "#121F3E", "#3b82f6": "#60A5FA",   # blue
    "#6d28d9": "#1E1739", "#a78bfa": "#A78BFA",   # violet
    "#4c1d95": "#1E1739",
    "#9f1239": "#2B121E", "#fb7185": "#FB7185",   # rose
    "#a16207": "#2C2109", "#facc15": "#F5B942",   # gold
    "#78350f": "#2C2109", "#f59e0b": "#F5B942",
    "#7f1d1d": "#2E1410", "#ef4444": "#FF6B3D",   # flame
    "#334155": "#1B2542", "#94a3b8": "#7C8AAF",   # neutral
    "#0e7490": "#0B2932", "#22d3ee": "#22D3EE",   # cyan
}


MERMAID_CONF = os.path.join(TOOLS, "mermaid.json")
DIAGRAM_DIR = os.path.join(TOOLS, "assets", "diagrams")
os.makedirs(DIAGRAM_DIR, exist_ok=True)


def render_diagram(src):
    """Compile a mermaid block to a PNG at build time.

    Every diagram bug in this repo came from text being laid out in one
    place and rendered in another: foreignObject clipping, a webfont
    arriving late, the build machine and the browser disagreeing about
    which font to measure. A raster image has no text to re-lay-out, so
    what is verified at build time is exactly what the reader sees. It
    cannot overlap, clip, reflow or flicker.

    Rendered at 3x for retina and displayed at its natural width.
    Cached by content hash, so only changed diagrams re-render.
    """
    import hashlib, subprocess, tempfile
    key = hashlib.md5(src.encode()).hexdigest()[:12]
    png = os.path.join(DIAGRAM_DIR, key + ".png")
    if not os.path.exists(png):
        mmdc = os.path.join(ROOT, "node_modules", ".bin", "mmdc")
        with tempfile.NamedTemporaryFile("w", suffix=".mmd", delete=False) as fh:
            fh.write(src)
            tmp = fh.name
        subprocess.run([mmdc, "-i", tmp, "-o", png, "-c", MERMAID_CONF,
                        "-b", "transparent", "-s", "3"], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.unlink(tmp)
    import struct
    with open(png, "rb") as fh:
        w, h = struct.unpack(">II", fh.read(24)[16:24])
    return (png, w // 3, h // 3)


def diagram_alt(src):
    """Describe a diagram from its own source.

    alt="Diagram" tells a search engine and a screen reader nothing. The node
    labels are the content, so build the description from them.
    """
    labels = re.findall(r'\[\"?(.*?)\"?\]', src)
    if not labels:
        labels = re.findall(r'\((.*?)\)', src)
    clean = []
    for lab in labels:
        lab = re.sub(r"<br\s*/?>", " ", lab)
        lab = re.sub(r"\s+", " ", lab).strip(' "')
        if lab and lab not in clean:
            clean.append(lab)
    if not clean:
        return "Diagram"
    # keep the first line of each node: that is the label, the rest is detail.
    # Long alt text is ignored by screen readers and diluted by search engines.
    heads = []
    for lab in clean:
        head = re.split(r"\s{2,}|·|\u00b7", lab)[0].strip()
        head = "".join(ch for ch in head
                       if unicodedata.category(ch)[0] != "S" or ch in "+-/&")
        head = re.sub(r"\s+", " ", head).strip(" -\u2014")
        if head:
            heads.append(head)
    kind = "Flowchart" if re.match(r"\s*(graph|flowchart)", src) else "Diagram"
    alt = f"{kind}: " + " \u2192 ".join(heads[:6])
    return alt[:180].rstrip(" \u2192") 


def retheme_mermaid(src):
    """Swap GitHub-theme hexes for palette equivalents, case-insensitively."""
    def sub(m):
        return MERMAID_PALETTE.get(m.group(0).lower(), m.group(0))
    return re.sub(r"#[0-9a-fA-F]{6}", sub, src)


def asset_version(name):
    """Content hash appended to asset URLs. Without this, GitHub Pages and the
    browser happily serve a cached style.css/app.js for hours, which makes a
    deployed fix look like it did nothing."""
    import hashlib
    path = os.path.join(TOOLS, "assets", name)
    with open(path, "rb") as fh:
        return hashlib.md5(fh.read()).hexdigest()[:8]


def slugify(text):
    text = re.sub(r"<[^>]+>", "", text)
    text = "".join(c for c in text if not unicodedata.category(c).startswith("So"))
    text = text.replace("&amp;", "and").replace("&", "and")
    text = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    return re.sub(r"[\s_]+", "-", text) or "section"


def md_to_html_path(src):
    """core/dsa.md -> core/dsa.html ;  roadmap/README.md -> roadmap/index.html"""
    if src == "README.md":
        return "index.html"
    d, f = os.path.split(src)
    f = "index.html" if f == "README.md" else f[:-3] + ".html"
    return os.path.join(d, f) if d else f


def rel(from_page, to_page):
    """Relative URL between two output paths."""
    base = os.path.dirname(from_page) or "."
    return os.path.relpath(to_page, base).replace(os.sep, "/")


def rewrite_link(href, page_dir):
    """Rewrite an in-repo markdown link to its built HTML equivalent."""
    if re.match(r"^(https?:|mailto:|#|//)", href):
        return href
    anchor = ""
    if "#" in href:
        href, anchor = href.split("#", 1)
        anchor = "#" + anchor
    if not href:
        return anchor
    target = os.path.normpath(os.path.join(page_dir, href))
    if href.endswith("/") or (not os.path.splitext(href)[1]):
        # directory link -> that directory's index page
        cand = os.path.join(target, "README.md")
        out = md_to_html_path(os.path.relpath(cand, ".")) if os.path.exists(
            os.path.join(ROOT, cand)) else os.path.join(target, "index.html")
    elif href.endswith(".md"):
        out = md_to_html_path(os.path.relpath(target, "."))
    else:
        return href + anchor
    out = os.path.normpath(out).replace(os.sep, "/")
    return rel(md_to_html_path(os.path.join(page_dir, "x.md")), out) + anchor


# ─────────────────────────────────────────────────────── inline pass ──

def inline(text, page_dir):
    out, i, n = [], 0, len(text)
    while i < n:
        ch = text[i]

        # inline code — protected from everything else
        if ch == "`":
            m = re.match(r"(`+)(.+?)\1", text[i:], re.S)
            if m:
                out.append("<code>%s</code>" % html.escape(m.group(2)))
                i += m.end()
                continue

        # raw html tag passthrough
        if ch == "<":
            m = re.match(r"</?[A-Za-z][^<>]*>", text[i:])
            if m:
                out.append(m.group(0))
                i += m.end()
                continue

        # image
        if ch == "!" and i + 1 < n and text[i + 1] == "[":
            m = re.match(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)", text[i:])
            if m:
                alt, src = m.group(1), m.group(2)
                cls = "badge" if "img.shields.io" in src else "md-img"
                out.append('<img class="%s" src="%s" alt="%s" loading="lazy">'
                           % (cls, html.escape(src, True), html.escape(alt, True)))
                i += m.end()
                continue

        # link
        if ch == "[":
            m = re.match(r"\[((?:[^\[\]]|\[[^\]]*\])*)\]\(([^()\s]+(?:\([^)]*\))?)\)", text[i:])
            if m:
                label, href = m.group(1), m.group(2)
                url = rewrite_link(href, page_dir)
                ext = ' target="_blank" rel="noopener"' if re.match(r"^https?:", url) else ""
                out.append('<a href="%s"%s>%s</a>' % (html.escape(url, True), ext,
                                                      inline(label, page_dir)))
                i += m.end()
                continue

        for pat, tag in ((r"\*\*\*(.+?)\*\*\*", "strong-em"), (r"\*\*(.+?)\*\*", "strong"),
                         (r"~~(.+?)~~", "del"), (r"(?<!\*)\*(?!\*)([^*]+?)\*(?!\*)", "em")):
            m = re.match(pat, text[i:], re.S)
            if m:
                inner = inline(m.group(1), page_dir)
                out.append("<strong><em>%s</em></strong>" % inner if tag == "strong-em"
                           else "<%s>%s</%s>" % (tag, inner, tag))
                i += m.end()
                break
        else:
            out.append(html.escape(ch) if ch in "&<>" else ch)
            i += 1
            continue
    return "".join(out)


# ──────────────────────────────────────────────────────── block pass ──

def render(md, page_dir):
    lines = md.split("\n")
    html_out, toc = [], []
    i, n = 0, len(lines)

    def close_lists(stack):
        while stack:
            html_out.append("</%s>" % stack.pop())

    list_stack = []

    while i < n:
        line = lines[i]
        stripped = line.strip()

        # ── code fence (supports 3+ backticks, nested) ──
        fence = re.match(r"^(`{3,})\s*([\w-]*)\s*$", stripped)
        if fence:
            close_lists(list_stack)
            marker, lang = fence.group(1), fence.group(2).lower()
            body, i = [], i + 1
            while i < n and not re.match(r"^`{%d,}\s*$" % len(marker), lines[i].strip()):
                body.append(lines[i])
                i += 1
            i += 1
            code = "\n".join(body)
            if lang == "mermaid":
                path, w, h = render_diagram(retheme_mermaid(code))
                alt = html.escape(diagram_alt(code))
                html_out.append(
                    '<figure class="mermaid-wrap"><img src="%sassets/diagrams/%s" '
                    'width="%d" height="%d" alt="%s" loading="lazy" '
                    'decoding="async"></figure>'
                    % ("../" * (page_dir.count("/") + 1) if page_dir else "",
                       os.path.basename(path), w, h, alt))
            else:
                html_out.append(
                    '<div class="code-block" data-lang="%s"><button class="copy" '
                    'aria-label="Copy code">Copy</button><pre><code>%s</code></pre></div>'
                    % (html.escape(lang or "text", True), html.escape(code)))
            continue

        # ── blank ──
        if not stripped:
            close_lists(list_stack)
            i += 1
            continue

        # ── GitHub alert ──
        alert = re.match(r"^>\s*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*$", stripped)
        if alert:
            close_lists(list_stack)
            kind, label = ALERTS[alert.group(1)]
            body, i = [], i + 1
            while i < n and lines[i].strip().startswith(">"):
                body.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            inner = render("\n".join(body), page_dir)[0]
            html_out.append('<div class="alert alert-%s"><p class="alert-label">%s</p>%s</div>'
                            % (kind, label, inner))
            continue

        # ── blockquote ──
        if stripped.startswith(">"):
            close_lists(list_stack)
            body = []
            while i < n and lines[i].strip().startswith(">"):
                body.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            html_out.append("<blockquote>%s</blockquote>" % render("\n".join(body), page_dir)[0])
            continue

        # ── table ──
        if stripped.startswith("|") and i + 1 < n and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1]):
            close_lists(list_stack)

            def cells(row):
                return [c.strip() for c in row.strip().strip("|").split("|")]

            head = cells(lines[i])
            aligns = []
            for spec in cells(lines[i + 1]):
                aligns.append("center" if spec.startswith(":") and spec.endswith(":")
                              else "right" if spec.endswith(":") else "left")
            i += 2
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append(cells(lines[i]))
                i += 1
            t = ['<div class="table-wrap"><table><thead><tr>']
            for k, h in enumerate(head):
                t.append('<th style="text-align:%s">%s</th>'
                         % (aligns[k] if k < len(aligns) else "left", inline(h, page_dir)))
            t.append("</tr></thead><tbody>")
            for r in rows:
                t.append("<tr>")
                for k, c in enumerate(r):
                    t.append('<td style="text-align:%s">%s</td>'
                             % (aligns[k] if k < len(aligns) else "left", inline(c, page_dir)))
                t.append("</tr>")
            t.append("</tbody></table></div>")
            html_out.append("".join(t))
            continue

        # ── heading ──
        head = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if head:
            close_lists(list_stack)
            level, text = len(head.group(1)), head.group(2).strip()
            sid = slugify(text)
            rendered = inline(text, page_dir)
            # Skip h3s in the centered page header (the tagline) — they sit before
            # the first h2 and would otherwise dominate the table of contents.
            if level == 2 or (level == 3 and any(t["level"] == 2 for t in toc)):
                # rendered is already HTML-escaped; strip tags then unescape
                # so entities like &amp; don't show up literally in the TOC.
                toc.append({"level": level, "id": sid,
                            "text": html.unescape(
                                re.sub(r"<[^>]+>", "", rendered)).strip()})
            anchor = ('<a class="hanchor" href="#%s" aria-label="Link to this section">#</a>' % sid
                      if level > 1 else "")
            html_out.append('<h%d id="%s">%s%s</h%d>' % (level, sid, rendered, anchor, level))
            i += 1
            continue

        # ── hr ──
        if re.match(r"^(---+|\*\*\*+|___+)$", stripped):
            close_lists(list_stack)
            html_out.append("<hr>")
            i += 1
            continue

        # ── list item ──
        li = re.match(r"^(\s*)([-*+]|\d+\.)\s+(.*)$", line)
        if li:
            indent = len(li.group(1))
            ordered = li.group(2).endswith(".")
            content = li.group(3)
            depth = indent // 2
            tag = "ol" if ordered else "ul"

            while len(list_stack) > depth + 1:
                html_out.append("</%s>" % list_stack.pop())
            if len(list_stack) == depth + 1 and list_stack[-1] != tag:
                html_out.append("</%s>" % list_stack.pop())
            if len(list_stack) < depth + 1:
                cls = ""
                if not ordered and re.match(r"^\[[ xX]\]\s", content):
                    cls = ' class="task-list"'
                html_out.append("<%s%s>" % (tag, cls))
                list_stack.append(tag)

            task = re.match(r"^\[([ xX])\]\s+(.*)$", content)
            if task:
                checked = " checked" if task.group(1).lower() == "x" else ""
                html_out.append(
                    '<li class="task"><input type="checkbox" disabled%s><span>%s</span></li>'
                    % (checked, inline(task.group(2), page_dir)))
            else:
                html_out.append("<li>%s</li>" % inline(content, page_dir))
            i += 1
            continue

        # ── raw html block line ──
        if RAW_HTML_RE.match(line):
            close_lists(list_stack)
            html_out.append(line)
            i += 1
            continue

        # ── paragraph ──
        close_lists(list_stack)
        para = []
        while i < n and lines[i].strip() and not re.match(
                r"^(\s*)([-*+]|\d+\.)\s+|^#{1,6}\s|^>|^\||^`{3,}|^(---+|\*\*\*+)$", lines[i]) \
                and not RAW_HTML_RE.match(lines[i]):
            para.append(lines[i].strip())
            i += 1
        if para:
            html_out.append("<p>%s</p>" % inline(" ".join(para), page_dir))
        else:
            html_out.append(line)
            i += 1

    close_lists(list_stack)
    return "\n".join(html_out), toc


# ────────────────────────────────────────────────────────── shell ──

def sidebar_html(current):
    parts = []
    for group, items in NAV:
        parts.append('<div class="nav-group"><p class="nav-label">%s</p><ul>' % html.escape(group))
        for src, label in items:
            page = md_to_html_path(src)
            active = ' class="active" aria-current="page"' if page == current else ""
            parts.append('<li><a href="%s"%s>%s</a></li>'
                         % (rel(current, page), active, html.escape(label)))
        parts.append("</ul></div>")
    return "".join(parts)


FLAT = [(md_to_html_path(s), l) for _, items in NAV for s, l in items]





def shell(*, page, title, description, body, toc, landing=False):
    depth = rel(page, "index.html")
    assets = os.path.dirname(depth) + "/" if os.path.dirname(depth) else ""
    idx = next((k for k, (p, _) in enumerate(FLAT) if p == page), None)

    pager = ""
    if idx is not None and not landing:
        prev_l = ('<a class="pager-link prev" href="%s"><span>Previous</span><strong>%s</strong></a>'
                  % (rel(page, FLAT[idx - 1][0]), html.escape(FLAT[idx - 1][1]))) if idx > 0 else "<div></div>"
        next_l = ('<a class="pager-link next" href="%s"><span>Next</span><strong>%s</strong></a>'
                  % (rel(page, FLAT[idx + 1][0]), html.escape(FLAT[idx + 1][1]))) if idx < len(FLAT) - 1 else "<div></div>"
        pager = '<nav class="pager">%s%s</nav>' % (prev_l, next_l)

    toc_html = ""
    if toc and not landing:
        items = "".join('<li class="lvl%d"><a href="#%s">%s</a></li>'
                        % (t["level"], t["id"], html.escape(t["text"])) for t in toc)
        toc_html = '<aside class="toc"><p class="toc-label">On this page</p><ul>%s</ul></aside>' % items

    src_md = next((s for _, items in NAV for s, _ in items if md_to_html_path(s) == page), None)
    edit = ""

    css_v = asset_version("style.css")
    js_v = asset_version("app.js")


    # Direct links in the header. `match` is the path prefix that lights the link
    # up, so a reader always knows which part of the site they're standing in.
    ICONS = {
        "Start":     "M13 2 4 14h6l-1 8 9-12h-6z",
        "Full map":  "M9 4 3 6v14l6-2 6 2 6-2V4l-6 2zM9 4v14M15 6v14",
        "Roadmap":   "M4 19h4v-6H4zM10 19h4V9h-4zM16 19h4V5h-4z",
        "Tracks":    "M4 7h16M4 12h16M4 17h9",
        "Skills":    "M12 3 3 8l9 5 9-5zM3 14l9 5 9-5",
        "Get hired": "M20 7H4a1 1 0 0 0-1 1v11a1 1 0 0 0 1 1h16a1 1 0 0 0 1-1V8a1 1 0 0 0-1-1M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2",
        "Guides":    "M4 5a2 2 0 0 1 2-2h12v18H6a2 2 0 0 1-2-2zM8 7h7M8 11h7",
    }
    topnav = "".join(
        '<a href="%s"%s><svg viewBox="0 0 24 24" aria-hidden="true">'
        '<path d="%s"/></svg><span>%s</span></a>'
        % (rel(page, target),
           ' class="on"' if (page == target or (match and page.startswith(match))) else "",
           ICONS[label], html.escape(label))
        for target, match, label in (
            ("START-HERE.html", None, "Start"),
            ("map.html", None, "Full map"),
            ("roadmap/index.html", "roadmap/", "Roadmap"),
            ("tracks/index.html", "tracks/", "Tracks"),
            ("core/index.html", "core/", "Skills"),
            ("placements/index.html", "placements/", "Get hired"),
            ("guides/index.html", "guides/", "Guides"),
        ))

    main = (('<main id="main" class="landing">%s</main>' % body) if landing else
            '<main id="main" class="content"><article class="prose">%s</article>%s%s</main>'
            % (body, edit, pager))

    return f"""<!doctype html>
<html lang="en" data-theme="brutalism">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(description)}">
<meta name="theme-color" content="#FFFFFF">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect width='100' height='100' fill='%23FFFF00' stroke='%23000000' stroke-width='10'/><text y='70' x='50' text-anchor='middle' font-size='56' font-family='monospace' font-weight='900' fill='%23000000'>T3</text></svg>">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,700;12..96,800;12..96,900&family=Space+Grotesk:wght@500;600;700&family=JetBrains+Mono:wght@400;600;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{assets}assets/style.css?v={css_v}">
<script>try{{var t=localStorage.getItem('t3-theme');if(t)document.documentElement.dataset.theme=t;else document.documentElement.dataset.theme='brutalism';}}catch(e){{}}</script>
</head>
<body class="{'is-landing' if landing else 'is-doc'}">
<a class="skip" href="#main">Skip to content</a>
<div class="read-progress" aria-hidden="true"><i></i></div>

<header class="topbar">
  <button class="icon-btn nav-toggle" aria-label="Open navigation" aria-expanded="false">
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h18M3 12h18M3 18h18"/></svg>
  </button>
  <a class="brand" href="{depth}">
    <span class="brand-mark" aria-hidden="true">[T3]</span>
    <span class="brand-text">Tier-3 <em>to</em> Top Tech</span>
  </a>
  <nav class="topnav" aria-label="Main">{topnav}</nav>
  <button class="search-trigger" data-search-open>
    <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
    <span>Search</span><kbd>⌘K</kbd>
  </button>
  <div class="topbar-actions">
    <a class="icon-btn" href="{REPO_URL}" target="_blank" rel="noopener" aria-label="View on GitHub" title="View on GitHub">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2a10 10 0 0 0-3.16 19.49c.5.09.68-.22.68-.48v-1.7c-2.78.6-3.37-1.34-3.37-1.34-.45-1.16-1.11-1.47-1.11-1.47-.91-.62.07-.6.07-.6 1 .07 1.53 1.03 1.53 1.03.9 1.53 2.34 1.09 2.91.83.09-.65.35-1.09.63-1.34-2.22-.25-4.55-1.11-4.55-4.94 0-1.09.39-1.98 1.03-2.68-.1-.25-.45-1.27.1-2.65 0 0 .84-.27 2.75 1.02a9.5 9.5 0 0 1 5 0c1.91-1.29 2.75-1.02 2.75-1.02.55 1.38.2 2.4.1 2.65.64.7 1.03 1.59 1.03 2.68 0 3.84-2.34 4.69-4.57 4.94.36.31.68.92.68 1.85v2.74c0 .27.18.58.69.48A10 10 0 0 0 12 2Z"/></svg>
    </a>
    <button class="theme-toggle" aria-label="Toggle theme (Current: Brutalism)" title="Theme: Brutalism — Click to switch theme">
      <svg class="i-brutal" viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="18" height="18" stroke="currentColor" stroke-width="2.5" fill="none"/><line x1="3" y1="9" x2="21" y2="9" stroke="currentColor" stroke-width="2.5"/><line x1="9" y1="21" x2="9" y2="9" stroke="currentColor" stroke-width="2.5"/></svg>
      <svg class="i-moon" viewBox="0 0 24 24" aria-hidden="true"><path d="M20 14.5A8.5 8.5 0 1 1 9.5 4a7 7 0 0 0 10.5 10.5Z" stroke="currentColor" stroke-width="2.5" fill="none"/></svg>
      <span class="theme-name">Brutalism</span>
    </button>
  </div>
</header>

<div class="layout">
  <aside class="sidebar" id="sidebar">
    <nav aria-label="Documentation">{'' if landing else sidebar_html(page)}</nav>
  </aside>
  <div class="scrim" data-close-nav></div>
  {main}
  {'' if landing else toc_html}
</div>

<div class="search-modal" hidden>
  <div class="search-backdrop" data-search-close></div>
  <div class="search-panel" role="dialog" aria-modal="true" aria-label="Search">
    <div class="search-field">
      <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
      <input type="search" placeholder="Search roadmaps, tracks, companies…" aria-label="Search" autocomplete="off">
      <kbd>Esc</kbd>
    </div>
    <div class="search-results" role="listbox"></div>
  </div>
</div>

<footer class="site-footer">
  <div class="foot-inner">
    <p class="foot-brand">Tier-3 <em>to</em> Top Tech</p>
    <p class="foot-note">Free forever, MIT licensed. Your college is a starting point, not a ceiling.</p>
    <p class="foot-links">
      <a href="{rel(page, 'START-HERE.html')}">Start here</a>
      <a href="{rel(page, 'map.html')}">Full map</a>
      <a href="{REPO_URL}" target="_blank" rel="noopener">GitHub</a>
      <a href="{REPO_URL}/issues/new" target="_blank" rel="noopener">Report a bug</a>
    </p>
  </div>
</footer>

<script>window.T3_BASE="{assets}";</script>
<script src="{assets}assets/app.js?v={js_v}" defer></script>
</body>
</html>"""


# ────────────────────────────────────────────────────────── build ──

def first_paragraph(md):
    for line in md.split("\n"):
        s = line.strip()
        if s and not s.startswith(("#", "<", ">", "-", "|", "!", "[", "*", "=")):
            return re.sub(r"[*`\[\]]|\(.*?\)", "", s)[:180]
    return "A free 4-year career roadmap for students in tier-3 engineering colleges."


def page_title(md, fallback):
    m = re.search(r"^#\s+(.+)$", md, re.M)
    if m:
        t = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        t = "".join(c for c in t if not unicodedata.category(c).startswith("So")).strip()
        return t or fallback
    return fallback


def main():
    if os.path.isdir(OUT):
        for name in os.listdir(OUT):
            if name != "CNAME":
                p = os.path.join(OUT, name)
                shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
    os.makedirs(os.path.join(OUT, "assets"), exist_ok=True)

    for asset in ("style.css", "app.js"):
        shutil.copy(os.path.join(TOOLS, "assets", asset), os.path.join(OUT, "assets", asset))
    open(os.path.join(OUT, ".nojekyll"), "w").close()

    index = []
    built = 0

    for _, items in NAV:
        for src, label in items:
            md = open(os.path.join(ROOT, src), encoding="utf-8").read()
            page = md_to_html_path(src)
            page_dir = os.path.dirname(src)
            title = f"{page_title(md, label)} · {SITE_TITLE}"
            desc = first_paragraph(md)

            if src == "README.md":
                body = open(os.path.join(TOOLS, "landing.html"), encoding="utf-8").read()
                out_html = shell(page=page, title=f"{SITE_TITLE} — The 4-Year Plan",
                                 description="A free 4-year career roadmap for engineering students.",
                                 body=body, toc=[], landing=True)
            else:
                body, toc = render(md, page_dir)
                out_html = shell(page=page, title=title, description=desc,
                                 body=body, toc=toc)
                index.append({
                    "t": title, "l": label, "u": page,
                    "h": [x["text"] for x in toc][:24],
                    "b": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))[:1400],
                })

            dest = os.path.join(OUT, page)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            open(dest, "w", encoding="utf-8").write(out_html)
            built += 1

    # ── the full map: every page in the repo on one screen ──
    tree_title = "The Complete Roadmap Map — Every Guide in One Place"
    tree_desc = ("A visual map of the whole placement preparation roadmap: the "
                 "4-year spine, 8 career tracks, core skills, hiring guides, "
                 "projects and templates — every page, one screen.")
    open(os.path.join(OUT, "map.html"), "w", encoding="utf-8").write(
        shell(page="map.html", title=tree_title, description=tree_desc,
              body=open(os.path.join(TOOLS, "tree.html"), encoding="utf-8").read(),
              toc=[], landing=True))
    built += 1

    # ── section index pages for directories linked as `dir/` ──
    for folder, (heading, blurb, nav_group) in SECTIONS.items():
        page = folder + "/index.html"
        items = next((its for grp, its in NAV if grp == nav_group), [])
        items = [(s, l) for s, l in items if s.startswith(folder + "/")]

        cards = []
        for src, label in items:
            md = open(os.path.join(ROOT, src), encoding="utf-8").read()
            m = re.search(r"^###\s+(.+)$", md, re.M)
            tag = re.sub(r"[*_`]", "", m.group(1)).strip() if m else first_paragraph(md)
            cards.append(
                '<a class="track" href="%s"><div class="track-top"><h3>%s</h3></div><p>%s</p></a>'
                % (rel(page, md_to_html_path(src)), html.escape(label), html.escape(tag)))

        body = (
            '<h1>%s</h1><p class="section-blurb">%s</p><div class="track-grid">%s</div>'
            % (html.escape(heading), html.escape(blurb), "".join(cards)))

        out_html = shell(page=page, title=f"{heading} · {SITE_TITLE}",
                         description=blurb, body=body, toc=[])
        dest = os.path.join(OUT, page)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        open(dest, "w", encoding="utf-8").write(out_html)
        built += 1

    json.dump(index, open(os.path.join(OUT, "assets", "search.json"), "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))

    shutil.copytree(DIAGRAM_DIR, os.path.join(OUT, "assets", "diagrams"),
                    dirs_exist_ok=True)
    print(f"Built {built} pages -> docs/")
    print(f"Search index: {len(index)} documents")


if __name__ == "__main__":
    main()
