"""Bring the Pi's config.py up to date without losing its calibration.

    python3 config_merge.py <new config.py> <kept config.py> [NAME,NAME…]

Settings new in <new> are added to the end of <kept> at their defaults (the
code reading them fails on a missing name). Each NAME given is copied from
<new> over <kept>'s: a value changed on purpose in the checkout.
"""
import ast
import sys


def settings(tree):
    """Top-level assignments: name -> the statement that sets it."""
    out = {}
    for node in tree.body:
        targets = (node.targets if isinstance(node, ast.Assign)
                   else [node.target] if isinstance(node, ast.AnnAssign) else [])
        for t in targets:
            for n in ast.walk(t):
                if isinstance(n, ast.Name):
                    out[n.id] = node
    return out


def main() -> None:
    new_path, kept_path = sys.argv[1:3]
    take = [n for n in (sys.argv[3] if len(sys.argv) > 3 else "").split(",") if n]
    new_src = open(new_path).read()
    new_lines = new_src.splitlines()
    new = settings(ast.parse(new_src))

    def text(node):
        return new_lines[node.lineno - 1:node.end_lineno]

    # values taken from the checkout, replaced in place, last first
    kept_src = open(kept_path).read()
    kept_lines = kept_src.splitlines()
    have = settings(ast.parse(kept_src))
    unknown = [n for n in take if n not in new]
    if unknown:
        sys.exit("  config.py: no setting " + ", ".join(unknown) + " in the checkout")
    replace = {}
    for n in take:
        if n in have:
            replace[id(have[n])] = (have[n], new[n])
    for old, src in sorted(replace.values(), key=lambda p: -p[0].lineno):
        kept_lines[old.lineno - 1:old.end_lineno] = text(src)
    if replace:
        open(kept_path, "w").write("\n".join(kept_lines) + "\n")

    # settings new in this version (a taken one missing on the Pi among them)
    have = settings(ast.parse(open(kept_path).read()))
    missing = {n: node for n, node in new.items() if n not in have}
    if missing:
        stmts = sorted({id(v): v for v in missing.values()}.values(), key=lambda v: v.lineno)
        with open(kept_path, "a") as f:
            f.write("\n# Added by deploy.sh: new in this version, at their defaults\n")
            for node in stmts:
                f.write("\n".join(text(node)) + "\n")
        print("  config.py: added " + ", ".join(sorted(missing)))
    final_src = open(kept_path).read()
    final_lines = final_src.splitlines()
    final = settings(ast.parse(final_src))
    for n in take:
        node = final[n]
        print("  config.py: " + final_lines[node.lineno - 1].split("#")[0].strip())


if __name__ == "__main__":
    main()
