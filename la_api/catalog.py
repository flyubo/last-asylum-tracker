"""Build a searchable index from recovered .proto schemas and message names."""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

MESSAGE_RE = re.compile(r"\\bmessage\\s+([A-Za-z_][A-Za-z0-9_]*)\\s*\\{")
FIELD_RE = re.compile(r"^\\s*(?:repeated\\s+|optional\\s+|map\\s*<[^>]+>\\s*)?([.A-Za-z_][.A-Za-z0-9_<> ,]*)\\s+([A-Za-z_][A-Za-z0-9_]*)\\s*=\\s*(\\d+)")


def extract_messages(proto_root: Path) -> dict[str, dict]:
    found: dict[str, dict] = {}
    for path in sorted(proto_root.rglob("*.proto")):
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        i = 0
        while i < len(lines):
            match = MESSAGE_RE.search(lines[i])
            if not match:
                i += 1
                continue
            name = match.group(1)
            depth = lines[i].count("{") - lines[i].count("}")
            block = [lines[i]]
            j = i + 1
            while j < len(lines) and depth > 0:
                block.append(lines[j])
                depth += lines[j].count("{") - lines[j].count("}")
                j += 1
            fields = []
            for line in block[1:]:
                fm = FIELD_RE.match(line.split("//", 1)[0])
                if fm:
                    fields.append({"type": fm.group(1).strip(), "name": fm.group(2), "number": int(fm.group(3))})
            found[name] = {"schema": path.name, "fields": fields}
            i = j
    return found


def build_catalog(proto_root: Path, names_file: Path) -> list[dict]:
    schemas = extract_messages(proto_root)
    names = []
    for line in names_file.read_text(encoding="utf-8", errors="replace").splitlines():
        name = line.strip().lstrip("-").strip()
        if name and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            names.append(name)
    result = []
    for name in sorted(set(names) | set(schemas)):
        direction = "request" if name.endswith("C2S") else "response" if name.endswith("S2C") else "other"
        schema = schemas.get(name, {})
        fields = schema.get("fields", [])
        result.append({
            "name": name,
            "direction": direction,
            "schema_file": schema.get("schema"),
            "fields": fields,
            "indexed": bool(schema),
            "search_text": " ".join([name, direction, schema.get("schema", ""), *(f["name"] for f in fields)]).lower(),
        })
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--proto-dir", required=True)
    parser.add_argument("--messages", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    catalog = build_catalog(Path(args.proto_dir), Path(args.messages))
    Path(args.output).write_text(
        json.dumps({"count": len(catalog), "apis": catalog}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    indexed = sum(1 for item in catalog if item["indexed"])
    print(f"Wrote {len(catalog)} API entries; {indexed} have matching protobuf schemas.")


if __name__ == "__main__":
    main()
