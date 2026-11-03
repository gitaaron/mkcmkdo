#!/usr/bin/env python3
"""Check the build markers in the docs, or show a doc as one build sees it.

The docs viewer (npm run docs) has a With UWB / Without UWB toggle. Most of
what it hides it finds on its own (build sections, link pairs, table rows);
the rest is marked in the markdown with HTML comments, which GitHub hides:

    <!--with_uwb-->…<!--/-->      on GitHub, and in the viewer with UWB
    <!--without_uwb-->…<!--/-->   on GitHub, and in the viewer without UWB
    <!--both-->…<!--/-->          on GitHub only (wording for both builds)
    <!--with_uwb: …-->            in the viewer with UWB only
    <!--without_uwb: …-->         in the viewer without UWB only

and the same for its servo drive switch (the Pi's PWM or the PTZ
controller), with a closer of its own so the two kinds can sit one inside
the other:

    <!--pigpio-->…<!--/servo-->   on GitHub, and in the viewer with that drive
    <!--arducam-->…<!--/servo-->
    <!--pigpio: …-->              in the viewer with that drive only
    <!--arducam: …-->
    | … <!--pigpio row--> … |     a table row for that drive only

Usage:
    python3 tools/check-build-markers.py                  check every doc
    python3 tools/check-build-markers.py --show with_uwb docs/design/04-electronics.md
                                                          print the doc as the viewer
                                                          sees it (or: without_uwb, github;
                                                          add a drive: with_uwb,arducam)
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGION = re.compile(r"<!--\s*(with_uwb|without_uwb|both)\s*-->([\s\S]*?)<!--\s*/\s*-->")
SERVO_REGION = re.compile(r"<!--\s*(pigpio|arducam)\s*-->([\s\S]*?)<!--\s*/servo\s*-->")
ONLY = re.compile(r"<!--(with_uwb|without_uwb|pigpio|arducam):([\s\S]*?)-->")
ROW = re.compile(r"<!--\s*(pigpio|arducam) row\s*-->")
ANY_MARK = re.compile(r"<!--\s*(?:with_uwb|without_uwb|both|pigpio|arducam|/|/servo)\s*-->"
                      r"|<!--(?:with_uwb|without_uwb|pigpio|arducam):")
SERVOS = ("pigpio", "arducam")
COMMENT = re.compile(r"<!--[\s\S]*?-->")
CODE = re.compile(r"^(```|~~~)[^\n]*\n[\s\S]*?^\1[^\n]*$|`[^`\n]+`", re.M)


def hide_code(md: str) -> tuple[str, list[str]]:
    """Markers inside code are literal text, on GitHub and in the viewer."""
    code: list[str] = []

    def stash(m):
        code.append(m.group(0))
        # keep the line count, so line numbers still match the file
        return f"\0{len(code) - 1}\0" + "\n" * m.group(0).count("\n")

    return CODE.sub(stash, md), code


def restore_code(md: str, code: list[str]) -> str:
    return re.sub(r"\0(\d+)\0\n*", lambda m: code[int(m.group(1))], md)


def view(md: str, build: str, servos: str = "pigpio") -> str:
    """The markdown as GitHub ("github") or the viewer in one build, with one
    servo drive, sees it."""
    md, code = hide_code(md)
    if build == "github":
        md = COMMENT.sub("", md)
    else:
        md = ONLY.sub(lambda m: re.sub(r"^ ", "", m.group(2)) if m.group(1) in (build, servos) else "", md)
        md = REGION.sub(lambda m: m.group(2) if m.group(1) == build else "", md)
        md = SERVO_REGION.sub(lambda m: m.group(2) if m.group(1) == servos else "", md)
        md = re.sub(r"^\|.*\n?", lambda m: row(m.group(0), servos), md, flags=re.M)
    return restore_code(md, code)


def row(line: str, servos: str) -> str:
    """A table row: gone if it is the other drive's, else without its tag."""
    m = ROW.search(line)
    if not m:
        return line
    return re.sub(r"\s*" + ROW.pattern, "", line) if m.group(1) == servos else ""


def check(path: Path) -> list[str]:
    md, _ = hide_code(path.read_text())
    rel = path.relative_to(ROOT)
    problems = []
    for m in ONLY.finditer(md):
        if "--" in m.group(2):
            problems.append(f"{rel}: '--' inside <!--{m.group(1)}: …--> ends the comment early on GitHub")
    # Regions of one kind don't nest, and every opener is closed. A build's
    # and a drive's can sit one inside the other: they have their own closers.
    for openers, closer in (("with_uwb|without_uwb|both", "/"), ("pigpio|arducam", "/servo")):
        depth = 0
        for m in re.finditer(rf"<!--\s*({openers}|{closer})\s*-->", md):
            line = md.count("\n", 0, m.start()) + 1
            if m.group(1) == closer:
                if depth == 0:
                    problems.append(f"{rel}:{line}: <!--{closer}--> with nothing open")
                depth = max(0, depth - 1)
            else:
                if depth:
                    problems.append(f"{rel}:{line}: markers don't nest")
                depth += 1
        if depth:
            problems.append(f"{rel}: a marker is never closed with <!--{closer}-->")
    lines = md.split("\n")
    for i, line in enumerate(lines):
        if ROW.search(line) and not line.lstrip().startswith("|"):
            problems.append(f"{rel}:{i + 1}: <!--… row--> belongs in a table row (a line starting with |)")
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not ANY_MARK.search(line) or not stripped.startswith("<!--"):
            continue
        # A line starting with a comment is an HTML block on GitHub: fine on a
        # line of its own between blank lines, wrong inside a paragraph.
        if re.fullmatch(r"<!--(with_uwb|without_uwb|pigpio|arducam):", stripped):
            after = ""  # opens a multi-line comment, closed by --> on a later line
        else:
            after = COMMENT.sub("", stripped).strip() if COMMENT.match(stripped) else stripped
        if after:
            problems.append(f"{rel}:{i + 1}: line starts with a marker — on GitHub it shows as raw HTML; "
                            "join it to the line before or put the marker on its own line")
        elif i > 0 and lines[i - 1].strip() and not ANY_MARK.match(lines[i - 1].strip()):
            problems.append(f"{rel}:{i + 1}: a marker on its own line needs a blank line before it")
    return problems


def docs() -> list[Path]:
    skip = {"node_modules", ".pytest_cache", ".dart_tool"}
    return sorted(p for p in ROOT.rglob("*.md") if not skip & set(p.parts))


def main() -> int:
    args = sys.argv[1:]
    if args[:1] == ["--show"]:
        build, _, servos = args[1].partition(",") if len(args) == 3 else ("", "", "")
        if build not in ("with_uwb", "without_uwb", "github") or servos not in ("", *SERVOS):
            print(__doc__)
            return 2
        print(view(Path(args[2]).read_text(), build, servos or "pigpio"))
        return 0
    problems = [p for d in docs() for p in check(d)]
    for p in problems:
        print(p)
    print(f"build markers: {len(problems)} problem(s)" if problems else "build markers: OK")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
