"""
Read real CSV data for the 20 case pack transactions
"""
import csv
import sys
import json
sys.stdout.reconfigure(encoding='utf-8')

# Transaction IDs from case_pack.csv
txn_ids = set([
    '3514030','3478782','3530164','3583227','3523199',
    '3476682','3514948','3558054','3581141','3506725',
    '3583368','3553342','3526826','3478561','3464869',
    '3534820','3450629','3491361','3503878','3509359'
])

# Card IDs to look for neighbors
card_ids = set([
    'C12382-K1','C11891-K1','C08623-K2','C08106-K1','C02923-K1',
    'C07297-K1','C09933-K2','C13171-K2','C08299-K1','C10434-K1',
    'C11923-K2','C05876-K2','C07671-K2','C13487-K1','C03042-K1',
    'C09988-K1','C04570-K1','C02354-K2','C07987-K2','C12265-K2'
])

print("=== STEP 1: Reading transactions.csv columns ===")
with open('transactions.csv', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    cols = reader.fieldnames
    print("Columns (first 25):", cols[:25] if cols else "NO COLS")

print("\n=== STEP 2: Finding flagged transactions ===")
found_txns = {}
with open('transactions.csv', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        tid = row.get('TransactionID', '')
        if tid in txn_ids:
            found_txns[tid] = dict(row)
        if len(found_txns) == len(txn_ids):
            break

print(f"Found {len(found_txns)}/{len(txn_ids)} flagged transactions")
for tid in sorted(txn_ids):
    r = found_txns.get(tid)
    if r:
        amt = r.get('TransactionAmt', '?')
        prod = r.get('ProductCD', '?')
        card = r.get('customer_id', r.get('card1', '?'))
        addr1 = r.get('addr1', '?')
        channel = r.get('channel', '?')
        ts = r.get('ts', '?')
        risk = r.get('risk_score', '?')
        cust = r.get('customer_id', '?')
        print(f"  {tid}: amt={amt}, prod={prod}, channel={channel}, addr1={addr1}, ts={ts}, risk={risk}, cust={cust}")
    else:
        print(f"  {tid}: NOT FOUND IN TRANSACTIONS")

print("\n=== STEP 3: Identity records for flagged txns ===")
found_identity = {}
with open('identity.csv', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    id_cols = reader.fieldnames
    print("Identity cols:", id_cols)
    for row in reader:
        tid = row.get('TransactionID', '')
        if tid in txn_ids:
            found_identity[tid] = dict(row)

print(f"Found {len(found_identity)} identity records for the 20 flagged txns")
for tid, rec in list(found_identity.items())[:5]:
    dev_info = rec.get('DeviceInfo', '?')
    dev_type = rec.get('DeviceType', '?')
    id_30 = rec.get('id_30', '?')
    id_31 = rec.get('id_31', '?')
    id_33 = rec.get('id_33', '?')
    id_15 = rec.get('id_15', '?')
    id_23 = rec.get('id_23', '?')
    print(f"  {tid}: device={dev_info}, OS={id_30}, browser={id_31}, screen={id_33}, new={id_15}, proxy={id_23}")
