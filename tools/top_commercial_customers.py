#!/usr/bin/env python3
"""Compute top commercial customers by recycled tonnage from source_seed.sql"""
import re
from pathlib import Path


def split_outside_quotes(s: str):
    parts = []
    cur = []
    in_quote = False
    quote_char = ""
    i = 0
    while i < len(s):
        ch = s[i]
        if ch in ("'", '"'):
            if not in_quote:
                in_quote = True
                quote_char = ch
                cur.append(ch)
            elif ch == quote_char:
                in_quote = False
                cur.append(ch)
            else:
                cur.append(ch)
        elif ch == "," and not in_quote:
            parts.append(''.join(cur).strip())
            cur = []
        else:
            cur.append(ch)
        i += 1
    if cur:
        parts.append(''.join(cur).strip())
    return parts


def parse_insert_blocks(text: str, table: str):
    # Find INSERT INTO rs.<table> ... (col1, col2) VALUES
    pattern = re.compile(rf"INSERT INTO\s+rs\.{re.escape(table)}\s*\((.*?)\)\s*VALUES", re.IGNORECASE | re.DOTALL)
    m = pattern.search(text)
    if not m:
        return [], []
    cols_raw = m.group(1)
    cols = [c.strip() for c in cols_raw.split(',')]
    # Find the VALUES block that follows the matched header
    start = m.end()
    # Find the terminating ');' for this VALUES block
    end_match = re.search(r"\);\s*", text[start:])
    if not end_match:
        return cols, []
    block = text[start:start + end_match.end()]
    # Extract tuples like (1, 'Name', ...), possibly across lines
    tuples = re.findall(r"\(([^)]*)\)\s*(?:,|;)", block, re.DOTALL)
    records = []
    for t in tuples:
        fields = split_outside_quotes(t)
        # clean quotes
        cleaned = []
        for f in fields:
            f = f.strip()
            if len(f) >= 2 and ((f[0] == "'" and f[-1] == "'") or (f[0] == '"' and f[-1] == '"')):
                cleaned.append(f[1:-1])
            else:
                cleaned.append(f)
        records.append(cleaned)
    return cols, records


def main():
    sql = Path('source_seed.sql').read_text()
    cust_cols, cust_rows = parse_insert_blocks(sql, 'DimCustomer')
    fact_cols, fact_rows = parse_insert_blocks(sql, 'FactPickupEvent')
    if not cust_rows or not fact_rows:
        print('Could not find inserts for DimCustomer or FactPickupEvent in source_seed.sql')
        return

    # build customer lookup
    cust_idx = {name: i for i, name in enumerate(cust_cols)}
    customers = {}
    for r in cust_rows:
        cid = int(r[cust_idx['CustomerId']])
        customers[cid] = {
            'CustomerName': r[cust_idx['CustomerName']],
            'CustomerType': r[cust_idx['CustomerType']]
        }

    fact_idx = {name: i for i, name in enumerate(fact_cols)}
    totals = {}
    for r in fact_rows:
        # Skip deleted facts
        is_deleted = r[fact_idx.get('IsDeleted', -1)]
        if is_deleted and is_deleted.strip() != '0':
            continue
        status = r[fact_idx['PickupStatus']]
        # consider only completed pickups
        if status.strip().strip("'") .lower() != 'completed':
            continue
        try:
            cid = int(r[fact_idx['CustomerId']])
        except Exception:
            continue
        recycled = r[fact_idx['RecycledWeightKg']]
        try:
            recycled = float(recycled)
        except Exception:
            recycled = 0.0
        totals[cid] = totals.get(cid, 0.0) + recycled

    # Filter commercial customers and convert to tonnes
    results = []
    for cid, kg in totals.items():
        cust = customers.get(cid)
        if not cust:
            continue
        if cust.get('CustomerType', '').lower() != 'commercial':
            continue
        tonnes = kg / 1000.0
        results.append((cid, cust['CustomerName'], tonnes))

    results.sort(key=lambda x: x[2], reverse=True)
    print('Top commercial customers by recycled tonnage (tonnes):')
    print(f"{'Rank':<4} {'CustomerId':<10} {'CustomerName':<30} {'Tonnes':>10}")
    for i, (cid, name, t) in enumerate(results[:10], start=1):
        print(f"{i:<4} {cid:<10} {name:<30} {t:10.3f}")


if __name__ == '__main__':
    main()
