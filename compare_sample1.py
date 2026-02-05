#!/usr/bin/env python3
"""Compare previous and new sample1 results"""
import json

# Load previous metadata
with open('samples/sample1/our_result_previous/metadata.json') as f:
    prev = json.load(f)

# Load new metadata  
with open('samples/sample1/our_result/metadata.json') as f:
    new = json.load(f)

# Load previous transcription
with open('samples/sample1/our_result_previous/final_transcription.txt') as f:
    prev_text = f.read()

# Load new transcription
with open('samples/sample1/our_result/final_transcription.txt') as f:
    new_text = f.read()

print('='*60)
print('COMPARISON: SEQUENTIAL vs PARALLEL')
print('='*60)
print()
print('PROCESSING TIME:')
print(f'  Previous (sequential): {prev["processing_time_seconds"]:.1f} seconds ({prev["processing_time_seconds"]/60:.1f} min)')
print(f'  New (parallel):        {new["processing_time_seconds"]:.1f} seconds ({new["processing_time_seconds"]/60:.1f} min)')
speedup = prev['processing_time_seconds'] / new['processing_time_seconds']
print(f'  Speedup:               {speedup:.1f}x faster!')
print()
print('OUTPUT LENGTH:')
print(f'  Previous: {len(prev_text):,} chars, {len(prev_text.splitlines())} lines')
print(f'  New:      {len(new_text):,} chars, {len(new_text.splitlines())} lines')
print()

# Check key medical terms preservation
terms = ['TEE', 'CT', 'PET', 'Ultrasound', 'DVT', 'IgG4', 'סרקואיד', 'אנדוקרדיטיס', 'לימפומה', 'ביופסיה']
print('MEDICAL TERMS PRESERVATION:')
for term in terms:
    prev_has = term in prev_text
    new_has = term in new_text
    status = 'OK' if prev_has == new_has else 'CHANGED'
    print(f'  [{status}] {term}: prev={prev_has}, new={new_has}')
