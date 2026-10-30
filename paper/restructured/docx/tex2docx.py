"""Turn paper/restructured/main.tex into a pandoc-friendly LaTeX body with literal
IEEE numbering (sections, tables, figures, references from main.aux)."""
import re, sys, os

root = sys.argv[1]            # paper/restructured
out = sys.argv[2]             # output .tex
src = open(os.path.join(root, "main.tex")).read()

# label -> number from main.aux
labels = {}
for k, v in re.findall(r"\\newlabel\{([^}#]+)\}\{\{(?:\\mbox\s*\{)?([^}]*)\}", open(os.path.join(root, "main.aux")).read()):
    labels[k] = v.strip()

# macros from numbers.tex
macros = dict(re.findall(r"\\newcommand\{\\(\w+)\}\{(.*)\}\s*$", open(os.path.join(root, "..", "numbers.tex")).read(), re.M))

# inline \input{tables/...}
src = re.sub(r"\\input\{(tables/[^}]+)\}", lambda m: open(os.path.join(root, m.group(1) + ".tex")).read(), src)

body = src[src.index("\\begin{abstract}"):src.index("\\bibliographystyle")]
abstract = re.search(r"\\begin\{abstract\}\s*(.*?)\s*\\end\{abstract\}", body, re.S).group(1)
keywords = re.search(r"\\begin\{IEEEkeywords\}\s*(.*?)\s*\\end\{IEEEkeywords\}", body, re.S).group(1)
body = body[body.index("\\end{IEEEkeywords}") + len("\\end{IEEEkeywords}"):]

def expand(s):
    s = re.sub(r"\\(\w+)\{\}", lambda m: macros.get(m.group(1), m.group(0)), s)
    for k, v in macros.items():
        s = re.sub(r"\\" + k + r"(?![A-Za-z])", lambda _m, v=v: v, s)
    return s
body, abstract = expand(body), expand(abstract)

# references
body = re.sub(r"\\ref\{([^}]+)\}", lambda m: labels[m.group(1)], body)

# section numbering
sec_n, sub_n = 0, 0
def roman(n):
    return ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"][n]
def heading(m):
    global sec_n, sub_n
    kind, star, title = m.group(1), m.group(2), m.group(3)
    if star:
        return f"\\section*{{{title}}}"
    if kind == "section":
        sec_n += 1; sub_n = 0
        return f"\\section*{{{roman(sec_n)}. {title}}}"
    sub_n += 1
    return f"\\subsection*{{{chr(64 + sub_n)}. {title}}}"
body = re.sub(r"\\(section|subsection)(\*?)\{([^}]*)\}(?:\\label\{[^}]*\})?", heading, body)

# table and figure captions: prefix the number
def float_env(m):
    env, text = m.group(1), m.group(2)
    lab = re.search(r"\\label\{([^}]+)\}", text)
    num = labels[lab.group(1)] if lab else "?"
    prefix = f"TABLE {num}. " if env.startswith("table") else f"Fig. {num}. "
    text = re.sub(r"\\caption\{", "\\\\caption{" + prefix.replace("\\", "\\\\"), text, count=1)
    return f"\\begin{{{env}}}{text}\\end{{{env}}}"
body = re.sub(r"\\begin\{(table\*?|figure\*?)\}(.*?)\\end\{\1\}", float_env, body, flags=re.S)

# figures: PNG versions
body = re.sub(r"\\includegraphics\[[^\]]*\]\{([^}]+)\.pdf\}", r"\\includegraphics[width=4.6in]{figures/\1.png}", body)

# findings as quoted blocks
body = re.sub(r"\\finding\{(\d+)\}\{(.*?)\}\n", r"\\begin{quote}\\textbf{Finding \1.} \2\\end{quote}\n", body, flags=re.S)

# contributions list with custom labels
body = body.replace("\\begin{enumerate}", "\\begin{itemize}").replace("\\end{enumerate}", "\\end{itemize}")
body = re.sub(r"\\item\[(C\d)\]", r"\\item \\textbf{\1.}", body)

# table helpers pandoc does not know
body = re.sub(r"\\shortstack\{([^}]*)\}", lambda m: m.group(1).replace("\\\\", " "), body)
body = body.replace("\\checkmark", "✓")
body = re.sub(r"\\setlength\{\\tabcolsep\}\{[^}]*\}", "", body)
body = re.sub(r"\\\\\[2pt\]\{\\scriptsize ([^}]*)\}", r"\n\n\\emph{\1}\n", body)   # footnotes below tables
body = re.sub(r">\{\\(raggedright|centering)\\arraybackslash\}", "", body)
body = body.replace("\\linebreakand", "")

body = body.replace("\\begin{table*}", "\\begin{table}").replace("\\end{table*}", "\\end{table}")
body = re.sub(r"\\mathit\{(\w+)\}", r"\1", body)
body = body.replace("\\sum_", "\\Sigma_")
doc = ("\\documentclass{article}\n\\usepackage{amsmath}\n\\begin{document}\n"
       "\\begin{abstract}" + abstract + "\\end{abstract}\n\n\\noindent\\textbf{\\textit{Index Terms}}---" + keywords + "\n\n" + body + "\n\\section*{References}\n\\end{document}\n")
open(out, "w").write(doc)
open(out + ".abstract", "w").write(abstract)
print("labels", len(labels), "macros", len(macros), "sections", sec_n)
