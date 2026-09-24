import csv

with open('case_pack.csv', encoding='utf-8') as f:
    cases = list(csv.DictReader(f))
flagged_ids = {c['flagged_txn_id']: c for c in cases}
print('Total cases in case_pack:', len(cases))

matches = {}
with open('identity.csv', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        tid = row['TransactionID']
        if tid in flagged_ids:
            matches[tid] = {
                'DeviceType': row['DeviceType'],
                'DeviceInfo': row['DeviceInfo'],
                'id_15': row['id_15'],
                'id_23': row['id_23'],
                'id_30': row['id_30'],
                'id_31': row['id_31'],
                'id_33': row['id_33'],
                'id_34': row['id_34']
            }

print(f'Matched identity rows: {len(matches)} / {len(flagged_ids)}')

# Check closed_cases_history for customer or card overlaps
with open('closed_cases_history.csv', encoding='utf-8') as f:
    closed_cases = list(csv.DictReader(f))

print(f'Total historical closed cases: {len(closed_cases)}')

case_customers = {c['customer_id']: c['case_id'] for c in cases}
case_cards = {c['card_id']: c['case_id'] for c in cases}

customer_hits = []
card_hits = []
for cc in closed_cases:
    if cc['customer_id'] in case_customers:
        customer_hits.append((cc['case_id'], cc['customer_id'], case_customers[cc['customer_id']], cc['outcome'], cc['pattern']))
    if cc['card_id'] in case_cards:
        card_hits.append((cc['case_id'], cc['card_id'], case_cards[cc['card_id']], cc['outcome'], cc['pattern']))

print(f'Historical closed cases matching same customer: {len(customer_hits)}')
for h in customer_hits[:10]:
    print('  Customer match:', h)

print(f'Historical closed cases matching same card: {len(card_hits)}')
for h in card_hits[:10]:
    print('  Card match:', h)

