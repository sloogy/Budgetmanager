import json
from pathlib import Path

LOCALES = [Path('locales/de.json'), Path('locales/en.json'), Path('locales/fr.json')]


def flatten(d, prefix=""):
    out = {}
    if isinstance(d, dict):
        for k, v in d.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            out.update(flatten(v, key))
    else:
        out[prefix] = d
    return out


def main():
    data = {}
    for p in LOCALES:
        if not p.exists():
            raise SystemExit(f"Missing locale file: {p}")
        with p.open('r', encoding='utf-8') as f:
            data[p.name] = flatten(json.load(f))

    base = data['de.json']
    results = []
    for name, d in data.items():
        missing = sorted([k for k in base.keys() if k not in d])
        extra = sorted([k for k in d.keys() if k not in base.keys()])
        results.append((name, len(d), len(missing), len(extra), missing[:10], extra[:10]))

    print("i18n key sync (flattened):")
    for name, total, m_cnt, e_cnt, m_s, e_s in results:
        print(f"- {name}: total={total} missing={m_cnt} extra={e_cnt}")
        if m_cnt:
            print(f"  missing sample: {m_s}")
        if e_cnt:
            print(f"  extra sample: {e_s}")


if __name__ == '__main__':
    main()
