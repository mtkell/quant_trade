import re

files = ["README.md", "CONTRIBUTING.md", "IMPROVEMENTS_PHASE2.md"]

for fname in files:
    with open(fname, "r", encoding="utf-8") as f:
        content = f.read()

    # Fix blanks around lists (MD032)
    content = re.sub(r"(\S)\n([-*] [^\n]+\n)", r"\1\n\n\2", content)

    # Fix blanks around fences (MD031)
    content = re.sub(r"(\S)\n(```)", r"\1\n\n```", content)
    content = re.sub(r"(```)\n(\S)", r"\1\n\n\2", content)

    # Add language to fenced code blocks (MD040)
    content = re.sub(r"\n```\n", r"\n```text\n", content)

    # Fix heading spacing (MD022)
    content = re.sub(r"(\S)\n(#+\s)", r"\1\n\n\2", content)

    # Wrap bare URLs
    content = content.replace("security@yourdomain.com", "<security@yourdomain.com>")

    with open(fname, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"✓ Fixed {fname}")

print("✓ All markdown errors fixed!")
