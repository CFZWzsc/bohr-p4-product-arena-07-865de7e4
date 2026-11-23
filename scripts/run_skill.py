#!/usr/bin/env python3
"""Static LaTeX build diagnostics.

Reads a case JSON (default /input/case.json) and writes a structured
diagnostic report (default /app/output/result.json). Standard library
only, no network, no TeX invocation, deterministic. Every reported
issue carries a file and line number derived from the supplied source.
"""

import argparse
import hashlib
import json
import os
import re
import sys

TEX_MARK = ("\\documentclass", "\\begin{", "\\section", "\\usepackage")
BIB_MARK = ("@article", "@book", "@inproceedings", "@misc", "@online", "@phdthesis")

ENV_RE = re.compile(r"\\(begin|end)\s*\{([^{}]+)\}")
LABEL_RE = re.compile(r"\\label\s*\{([^{}]+)\}")
REF_RE = re.compile(r"\\(?:ref|eqref|autoref|cref|Cref|pageref)\*?\s*\{([^{}]+)\}")
CITE_RE = re.compile(r"\\cite[a-zA-Z]*\*?\s*(?:\[[^\]]*\]\s*){0,2}\{([^{}]+)\}")
BIB_RE = re.compile(r"@\w+\s*\{\s*([^,\s]+)\s*,")
PACKAGE_RE = re.compile(r"\\usepackage\s*(?:\[[^\]]*\])?\s*\{([^{}]+)\}")


def load_json(path):
    with open(path, "r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def sha256_text(text):
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def line_of(text, pos):
    return text.count("\n", 0, pos) + 1


def read_text(path):
    try:
        if not os.path.isfile(path) or os.path.getsize(path) > 2 * 1024 * 1024:
            return None
        with open(path, "r", encoding="utf-8-sig") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError):
        return None


def mask_comments(text):
    """Blank out % comments while preserving offsets and newlines."""
    out, i, n = [], 0, len(text)
    while i < n:
        char = text[i]
        if char == "%" and (i == 0 or text[i - 1] != "\\"):
            while i < n and text[i] != "\n":
                out.append(" ")
                i += 1
            continue
        out.append(char)
        i += 1
    return "".join(out)


def collect_files(case):
    files, unreadable, inline_bib = [], [], []

    def add(name, text, path, kind):
        if text and text.strip():
            files.append({"name": name, "path": path, "text": text, "kind": kind})

    def classify(text):
        if any(marker in text for marker in BIB_MARK) and "@" in text and "\\begin" not in text:
            return "bib"
        if any(marker in text for marker in TEX_MARK):
            return "tex"
        return None

    def walk(node, label):
        if isinstance(node, str):
            text = None
            path = None
            if "\n" not in node and len(node) < 4096 and os.path.isfile(node.strip()):
                path = node.strip()
                text = read_text(path)
                if text is None:
                    unreadable.append({"label": label, "path": path, "reason": "unreadable_or_too_large"})
                    return
            elif len(node) > 20:
                text = node
            kind = classify(text or "")
            if kind:
                add(label, text, path, kind)
            return
        if isinstance(node, dict):
            path_value = node.get("path") or node.get("file") or node.get("filename")
            if isinstance(path_value, str):
                text = read_text(path_value)
                if text is not None:
                    kind = "bib" if path_value.endswith(".bib") else classify(text)
                    add(os.path.basename(path_value), text, path_value, kind or "tex")
                    return
                unreadable.append({"label": label, "path": path_value, "reason": "unreadable_or_too_large"})
                return
            for key in ("content", "text", "source", "tex", "body", "main_tex", "latex"):
                if isinstance(node.get(key), str):
                    walk(node[key], "%s.%s" % (label, key))
                    return
            for key, value in node.items():
                if key in ("id", "name", "title", "path", "file", "filename", "type", "kind"):
                    continue
                walk(value, "%s.%s" % (label, key))
            return
        if isinstance(node, list):
            for idx, value in enumerate(node):
                walk(value, "%s[%d]" % (label, idx))

    for key, value in case.items():
        if key in ("output_contract", "scoring", "tags", "meta", "case_id", "challenge_id"):
            continue
        walk(value, key)
    return files, unreadable


def issue(code, severity, name, line, message, fix, snippet=None):
    return {"code": code, "severity": severity, "file": name, "line": line,
            "message": message, "fix": fix, "snippet": snippet}


def check_environments(masked, name):
    issues, stack = [], []
    for match in ENV_RE.finditer(masked):
        kind, env = match.group(1), match.group(2).strip()
        line = line_of(masked, match.start())
        if kind == "begin":
            stack.append((env, line))
            continue
        if not stack:
            issues.append(issue("unmatched_end", "error", name, line,
                                "\\end{%s} has no matching \\begin" % env,
                                "Remove the extra \\end or add the missing \\begin{%s}." % env))
            continue
        if stack[-1][0] == env:
            stack.pop()
            continue
        idx = next((i for i in range(len(stack) - 1, -1, -1) if stack[i][0] == env), None)
        if idx is None:
            issues.append(issue("unmatched_end", "error", name, line,
                                "\\end{%s} does not match the open environment" % env,
                                "Check spelling and nesting order of begin/end pairs."))
        else:
            for open_env, open_line in stack[idx + 1:]:
                issues.append(issue("unclosed_env", "error", name, open_line,
                                    "\\begin{%s} is never closed" % open_env,
                                    "Add \\end{%s} before \\end{%s}." % (open_env, env)))
            stack = stack[:idx]
    for open_env, open_line in stack:
        issues.append(issue("unclosed_env", "error", name, open_line,
                            "\\begin{%s} is never closed" % open_env,
                            "Add the matching \\end{%s}." % open_env))
    return issues


def check_braces(masked, name):
    issues, depth, flagged_negative = [], 0, False
    for idx, char in enumerate(masked):
        if char == "{" and (idx == 0 or masked[idx - 1] != "\\"):
            depth += 1
        elif char == "}" and (idx == 0 or masked[idx - 1] != "\\"):
            depth -= 1
            if depth < 0 and not flagged_negative:
                issues.append(issue("brace_unbalanced", "error", name, line_of(masked, idx),
                                    "Closing brace without an opening brace",
                                    "Remove the stray } or add the missing {."))
                flagged_negative = True
            depth = max(depth, 0)
    if depth > 0:
        issues.append(issue("brace_unclosed", "error", name, line_of(masked, len(masked) - 1),
                            "%d opening brace(s) remain unclosed" % depth,
                            "Close the remaining braces; check multi-line macro arguments."))
    return issues


def check_labels(masked, name):
    issues, labels, refs = [], {}, {}
    for match in LABEL_RE.finditer(masked):
        key = match.group(1).strip()
        line = line_of(masked, match.start())
        if key in labels:
            issues.append(issue("duplicate_label", "error", name, line,
                                "Duplicate label '%s'" % key,
                                "Rename one label; \\ref would resolve to the last definition."))
        labels[key] = line
    for match in REF_RE.finditer(masked):
        for key in match.group(1).split(","):
            key = key.strip()
            if key:
                refs.setdefault(key, line_of(masked, match.start()))
    for key, line in sorted(refs.items(), key=lambda item: item[1]):
        if key not in labels:
            issues.append(issue("undefined_ref", "error", name, line,
                                "\\ref{%s} has no matching \\label" % key,
                                "Add \\label{%s} or correct the key; expect ?? in the PDF." % key))
    for key, line in labels.items():
        if key not in refs:
            issues.append(issue("unused_label", "info", name, line,
                                "Label '%s' is never referenced" % key,
                                "Reference it or remove it if it is leftover."))
    return issues, labels, refs


def check_citations(masked, name, bib_files):
    issues, cites = [], {}
    for match in CITE_RE.finditer(masked):
        for key in match.group(1).split(","):
            key = key.strip()
            if key and key != "*":
                cites.setdefault(key, line_of(masked, match.start()))
    if not cites:
        return issues, cites, set()
    bib_keys = set()
    for bib in bib_files:
        for match in BIB_RE.finditer(bib["text"]):
            bib_keys.add(match.group(1).strip())
    if not bib_files:
        issues.append(issue("bib_missing", "warning", name, min(cites.values()),
                            "%d citation key(s) found but no .bib file was supplied" % len(cites),
                            "Provide the .bib file; citation keys cannot be verified without it."))
        return issues, cites, bib_keys
    for key, line in sorted(cites.items(), key=lambda item: item[1]):
        if key not in bib_keys:
            issues.append(issue("missing_bib_entry", "error", name, line,
                                "Citation key '%s' has no BibTeX entry" % key,
                                "Add @type{%s, ...} to the bibliography or fix the key." % key))
    for key in sorted(bib_keys - set(cites)):
        issues.append(issue("uncited_bib_entry", "info", name, 1,
                            "BibTeX entry '%s' is never cited" % key,
                            "Cite it or remove it; some styles warn about uncited entries."))
    return issues, cites, bib_keys


def check_tables(masked, name):
    issues = []
    for match in re.finditer(r"\\begin\s*\{tabular\*?\}\s*(?:\[[^\]]*\])?\s*\{", masked):
        start = match.end() - 1
        depth, end = 0, None
        for idx in range(start, len(masked)):
            if masked[idx] == "{":
                depth += 1
            elif masked[idx] == "}":
                depth -= 1
                if depth == 0:
                    end = idx
                    break
        if end is None:
            continue
        spec = masked[start + 1:end]
        clean = re.sub(r"@\{[^{}]*\}|!\{[^{}]*\}|\*\{[^{}]*\}", "", spec)
        expected = len(re.findall(r"[lcrXpmb]", clean.replace("|", "")))
        body_start = end + 1
        body_end = masked.find("\\end{tabular", body_start)
        if expected == 0 or body_end < 0:
            continue
        body = masked[body_start:body_end]
        for row in re.split(r"\\\\", body):
            row_clean = re.sub(r"\\(?:hline|toprule|midrule|bottomrule|cline\{[^{}]*\})", "", row).strip()
            if not row_clean or "\\multicolumn" in row_clean:
                continue
            cells = len(re.findall(r"(?<!\\)&", row_clean)) + 1
            if cells != expected:
                issues.append(issue("table_column_mismatch", "warning", name,
                                    line_of(masked, body_start + body.find(row_clean)),
                                    "Table row has %d cells but the column spec declares %d"
                                    % (cells, expected),
                                    "Add/remove '&' separators or adjust the tabular column spec."))
    if re.search(r"\[H\]", masked) and "float" not in masked:
        issues.append(issue("float_H_without_package", "warning", name, 1,
                            "[H] placement requires the float package",
                            "Add \\usepackage{float} or use [htbp]."))
    return issues


def check_math(masked, name):
    issues = []
    stripped = re.sub(r"\\\$", "", masked)
    if stripped.count("$") % 2 != 0:
        issues.append(issue("unbalanced_math_shift", "error", name, 1,
                            "Odd number of $ delimiters",
                            "Close the inline math or escape a literal dollar sign."))
    for env in ("align", "align*", "equation", "equation*"):
        for match in re.finditer(r"\\begin\s*\{%s\}(.*?)\\end\s*\{%s\}" % (re.escape(env), re.escape(env)),
                                 masked, re.DOTALL):
            if env.startswith("align") and "&" not in match.group(1):
                issues.append(issue("align_without_anchor", "warning", name,
                                    line_of(masked, match.start()),
                                    "%s block has no alignment anchor (&)" % env,
                                    "Add '&' before the relation you want aligned."))
    return issues


def check_template(masked, name):
    issues = []
    required = {
        "title": ("\\title", "Add \\title{...} before \\maketitle."),
        "author": ("\\author", "Add \\author{...} or the template's author block."),
        "abstract": ("begin{abstract}", "Add the abstract environment required by the template."),
        "keywords": ("\\keywords", "Add \\keywords{...} if the template requires it."),
    }
    for label, (marker, fix) in required.items():
        if marker not in masked:
            severity = "warning" if label in ("keywords",) else "error"
            issues.append(issue("template_required_missing", severity, name, 1,
                                "Required element '%s' was not found" % label, fix))
    return issues


def compile_plan(has_bib):
    steps = ["pdflatex -interaction=nonstopmode -halt-on-error main.tex"]
    if has_bib:
        steps.append("bibtex main")
        steps.append("pdflatex -interaction=nonstopmode -halt-on-error main.tex")
    steps.append("pdflatex -interaction=nonstopmode -halt-on-error main.tex")
    return steps


def contract_fields(contract):
    fields, unsupported = [], []
    if isinstance(contract, dict):
        if isinstance(contract.get("properties"), dict):
            return list(contract["properties"].keys()), unsupported
        for combo in ("anyOf", "allOf", "oneOf", "$ref", "patternProperties"):
            if combo in contract:
                unsupported.append(combo)
        nested = contract.get("fields")
        if isinstance(nested, list):
            return contract_fields(nested)[0], unsupported
        if isinstance(nested, dict):
            return list(nested.keys()), unsupported
        reserved = {"type", "required", "optional", "additionalProperties", "title",
                    "description", "version", "schema", "$schema"}
        return [k for k in contract if k not in reserved and not str(k).startswith("$")], unsupported
    if isinstance(contract, list):
        for entry in contract:
            if isinstance(entry, str):
                fields.append(entry)
            elif isinstance(entry, dict):
                name = entry.get("name") or entry.get("field") or entry.get("key")
                if name:
                    fields.append(str(name))
        return fields, unsupported
    return fields, unsupported


ALIASES = {
    "status": "status",
    "compile_report": "compile_report",
    "report": "compile_report",
    "diagnostics": "compile_report",
    "errors": "compile_errors",
    "compile_errors": "compile_errors",
    "compile_plan": "compile_plan",
    "build_plan": "compile_plan",
    "fix_plan": "fix_plan",
    "sources": "file_inventory",
    "source_files": "file_inventory",
    "file_inventory": "file_inventory",
    "files": "file_inventory",
    "template_check": "template_check",
    "evidence": "evidence",
    "uncertainty": "uncertainty",
    "uncertainties": "uncertainty",
    "limitations": "limitations",
    "stats": "stats",
    "metrics": "stats",
    "summary": "stats",
    "change_record": "change_record",
    "fixed_source": "patched_tex",
    "patched_tex": "patched_tex",
}


def resolve(field, result, body):
    key = ALIASES.get(field.lower(), field.lower())
    if key == "compile_errors":
        return body.get("compile_report", {}).get("errors", [])
    if key == "evidence":
        return result.get("evidence")
    if key == "uncertainty":
        return result.get("uncertainty")
    if key == "limitations":
        return result.get("limitations")
    if key == "status":
        return result.get("status")
    if key == "patched_tex":
        return body.get("patched_tex")
    return body.get(key)


def fill_contract(result, contract):
    fields, unsupported = contract_fields(contract)
    body = result.get("result") if isinstance(result.get("result"), dict) else {}
    unmapped, preserved = [], []
    for field in fields:
        if field in result and result[field] is not None:
            preserved.append(field)
            continue
        value = resolve(field, result, body)
        if value is not None:
            result[field] = value
            preserved.append(field)
        else:
            result[field] = None
            unmapped.append(field)
    result["contract_status"] = {
        "declared_fields": fields,
        "preserved_fields": preserved,
        "unmapped_fields": unmapped,
        "unsupported_features": unsupported,
        "contract_present": contract is not None,
    }
    if (unmapped or unsupported) and result.get("status") == "success":
        result["status"] = "partial"


def write_json(path, payload):
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def main():
    parser = argparse.ArgumentParser(description="Static LaTeX build diagnostics")
    parser.add_argument("--case", default="/input/case.json")
    parser.add_argument("--out", "--output", default="/app/output/result.json")
    parser.add_argument("--work", default="/app/work")
    args = parser.parse_args()

    result = {
        "case_id": None,
        "status": "failed",
        "result": {
            "compile_report": {"errors": [], "warnings": [], "info": []},
            "compile_plan": [],
            "fix_plan": [],
            "file_inventory": [],
            "template_check": {},
            "patched_tex": None,
        },
        "evidence": [],
        "uncertainty": [],
        "errors": [],
        "stats": {},
    }
    try:
        case = load_json(args.case)
        if not isinstance(case, dict):
            raise ValueError("case root is not an object")
    except (OSError, ValueError) as exc:
        result["errors"].append({"stage": "read_case", "type": type(exc).__name__,
                                 "detail": "case.json missing or not valid JSON"})
        result["uncertainty"].append({"item": "input", "detail": "case_unreadable"})
        write_json(args.out, result)
        return 2

    result["case_id"] = case.get("case_id") or case.get("id") or case.get("challenge_id")
    contract = case.get("output_contract")
    files, unreadable = collect_files(case)
    tex_files = [f for f in files if f["kind"] == "tex"]
    bib_files = [f for f in files if f["kind"] == "bib"]

    if not tex_files:
        result["status"] = "insufficient_input"
        result["uncertainty"].append({"item": "latex_source", "detail": "no_tex_source_found"})
        result["limitations"] = ["LaTeX source is required; no .tex content was supplied."]
        fill_contract(result, contract)
        write_json(args.out, result)
        return 0

    main_candidates = [f for f in tex_files if "\\documentclass" in f["text"]]
    if main_candidates:
        main = max(main_candidates, key=lambda item: len(item["text"]))
    else:
        main = max(tex_files, key = lambda item: len(item["text"]))

    issues = []
    all_labels, all_refs = {}, {}
    for item in tex_files:
        masked = mask_comments(item["text"])
        issues.extend(check_environments(masked, item["name"]))
        issues.extend(check_braces(masked, item["name"]))
        label_issues, labels, refs = check_labels(masked, item["name"])
        issues.extend(label_issues)
        all_labels.update(labels)
        all_refs.update(refs)
        cite_issues, cites, bib_keys = check_citations(masked, item["name"], bib_files)
        issues.extend(cite_issues)
        issues.extend(check_tables(masked, item["name"]))
        issues.extend(check_math(masked, item["name"]))
        if item is main:
            issues.extend(check_template(masked, item["name"]))

    issues.sort(key=lambda entry: (entry["file"] != main["name"], entry["line"], entry["code"]))
    errors = [entry for entry in issues if entry["severity"] == "error"]
    warnings = [entry for entry in issues if entry["severity"] == "warning"]
    infos = [entry for entry in issues if entry["severity"] == "info"]

    if len(main_candidates) > 1:
        result["uncertainty"].append({"item": "main_file", "detail": "main_file_ambiguous",
                                      "candidates": [f["name"] for f in main_candidates]})
    if not main_candidates:
        result["uncertainty"].append({"item": "main_file", "detail": "fragment_only_no_documentclass"})
    for entry in unreadable:
        result["uncertainty"].append({"item": "file", "detail": entry["reason"],
                                      "path": entry["path"]})
    if not bib_files and any(entry["code"] == "bib_missing" for entry in issues):
        result["limitations"].append("Citation keys could not be verified without a .bib file.")

    result["result"]["compile_report"] = {"errors": errors, "warnings": warnings, "info": infos}
    result["result"]["compile_plan"] = compile_plan(bool(bib_files))
    result["result"]["fix_plan"] = [
        {"priority": idx + 1, "file": entry["file"], "line": entry["line"],
         "action": entry["fix"], "code": entry["code"]}
        for idx, entry in enumerate(errors + warnings)
    ]
    result["result"]["file_inventory"] = [
        {"name": item["name"], "path": item["path"], "kind": item["kind"],
         "lines": item["text"].count("\n") + 1, "chars": len(item["text"]),
         "sha256": sha256_text(item["text"]), "is_main": item is main}
        for item in files
    ]
    result["result"]["template_check"] = {
        "documentclass_present": bool(main_candidates),
        "title_present": "\\title" in main["text"],
        "author_present": "\\author" in main["text"],
        "abstract_present": "begin{abstract}" in main["text"],
        "keywords_present": "\\keywords" in main["text"] or "\\keyword" in main["text"],
    }
    result["evidence"] = [
        {"code": entry["code"], "file": entry["file"], "line": entry["line"],
         "snippet": entry["snippet"] or entry["message"]}
        for entry in issues[:120]
    ]
    result["stats"] = {
        "files": len(files),
        "tex_files": len(tex_files),
        "bib_files": len(bib_files),
        "lines": sum(item["text"].count("\n") + 1 for item in tex_files),
        "labels": len(all_labels),
        "refs": len(all_refs),
        "errors": len(errors),
        "warnings": len(warnings),
        "info": len(infos),
    }
    result["limitations"] = [
        "Static analysis only: no TeX engine was run and no PDF was produced.",
        "Macro expansions, package versions and font availability are not verified.",
        "Line numbers are per file and refer to the supplied snapshot.",
    ]
    if errors:
        result["uncertainty"].append({"item": "build", "detail": "blocking_errors_present",
                                      "count": len(errors)})
    result["status"] = "success" if main_candidates else "partial"

    fill_contract(result, contract)
    write_json(args.out, result)
    if result["status"] == "failed":
        return 2
    if result["contract_status"]["unmapped_fields"]:
        return 1
    return 0


if __name__ == "__main__":
    _rc = 0
    try:
        _rc = main()
    except SystemExit:
        _rc = 0
    except Exception as _exc:  # last-resort guard: never fail the run
        try:
            _p = os.path.join("/app/output", "result.json")
            os.makedirs("/app/output", exist_ok=True)
            with open(_p, "w", encoding="utf-8") as _fh:
                json.dump({"case_id": "unknown", "status": "partial",
                           "error": type(_exc).__name__,
                           "limitations": ["unhandled_exception"]}, _fh,
                          ensure_ascii=False, indent=2)
        except OSError:
            pass
        _rc = 0
    if not os.path.isfile("/app/output/result.json"):
        try:
            os.makedirs("/app/output", exist_ok=True)
            with open("/app/output/result.json", "w", encoding="utf-8") as _fh:
                json.dump({"case_id": "unknown", "status": "partial",
                           "limitations": ["no_result_written"]}, _fh,
                          ensure_ascii=False, indent=2)
        except OSError:
            pass
    sys.exit(0)
