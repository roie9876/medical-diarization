#!/usr/bin/env python3
"""Compare old and new transcription results"""

import subprocess
import difflib

# Get old result from git
old_result = subprocess.check_output(
    ['git', 'show', 'bcb2634:samples/sample2/our_result/final_transcription.txt'], 
    text=True
)

# Get new result
with open('samples/sample2/our_result/final_transcription.txt', 'r') as f:
    new_result = f.read()

# Get ground truth
with open('samples/sample2/ground_truth.txt', 'r') as f:
    ground_truth = f.read()

print('='*70)
print('COMPARISON: OLD vs NEW vs GROUND TRUTH')
print('='*70)
print()
print(f'Old result: {len(old_result)} chars, {len(old_result.splitlines())} lines')
print(f'New result: {len(new_result)} chars, {len(new_result.splitlines())} lines')
print(f'Ground truth: {len(ground_truth)} chars, {len(ground_truth.splitlines())} lines')
print()

# Line by line comparison
old_lines = old_result.strip().splitlines()
new_lines = new_result.strip().splitlines()
gt_lines = ground_truth.strip().splitlines()

print('='*70)
print('DIFFERENCES: OLD vs NEW')
print('='*70)
print()

diff = list(difflib.unified_diff(old_lines, new_lines, lineterm='', fromfile='OLD', tofile='NEW'))
if diff:
    for line in diff:
        print(line)
else:
    print('NO DIFFERENCES!')

print()
print('='*70)
print('KEY CHANGES ANALYSIS')
print('='*70)

# Count matching lines
matches_old = 0
matches_new = 0
for gt_line in gt_lines:
    gt_text = gt_line.split(']: ', 1)[-1] if ']: ' in gt_line else gt_line
    for old_line in old_lines:
        old_text = old_line.split(']: ', 1)[-1] if ']: ' in old_line else old_line
        if gt_text.strip() in old_text.strip() or old_text.strip() in gt_text.strip():
            matches_old += 1
            break
    for new_line in new_lines:
        new_text = new_line.split(']: ', 1)[-1] if ']: ' in new_line else new_line
        if gt_text.strip() in new_text.strip() or new_text.strip() in gt_text.strip():
            matches_new += 1
            break

print(f'\nGround truth lines: {len(gt_lines)}')
print(f'Old result matching lines (approx): {matches_old}')
print(f'New result matching lines (approx): {matches_new}')

# Check for specific issues
print('\n--- Specific checks ---')

# Check if patient answer "אותה רגל" is present
if 'אותה רגל' in new_result and old_result.count('[מטופל]: אותה רגל') != new_result.count('[מטופל]: אותה רגל'):
    print("⚠️  Patient line 'אותה רגל' changed")

# Check if "43" or "ארבעים ושלוש" is present
if '43' in old_result and '43' not in new_result:
    print("⚠️  Age '43' changed to text")
elif '43' in new_result:
    print("✓ Age '43' preserved")

# Check for בן משפחה speaker
old_family = old_result.count('[בן משפחה]')
new_family = new_result.count('[בן משפחה]')
print(f'Family member lines - Old: {old_family}, New: {new_family}')

# Check for medication names
meds = ['Lipitor', 'Euthyrox', 'DVT', 'Ultrasound']
for med in meds:
    old_has = med in old_result
    new_has = med in new_result
    gt_has = med in ground_truth
    status = '✓' if (new_has and gt_has) else ('⚠️' if gt_has and not new_has else '✓')
    print(f'{status} {med}: GT={gt_has}, Old={old_has}, New={new_has}')

print()
print('='*70)
print('VERDICT')
print('='*70)
if len(new_result) < len(old_result) * 0.8:
    print('⚠️  WARNING: New result is significantly shorter!')
elif len(new_result) > len(old_result) * 1.2:
    print('⚠️  WARNING: New result is significantly longer!')
else:
    print('✓ Result lengths are comparable')

# Check line counts
if len(new_lines) < len(old_lines) - 3:
    print(f'⚠️  WARNING: Lost {len(old_lines) - len(new_lines)} lines')
elif len(new_lines) > len(old_lines) + 3:
    print(f'ℹ️  INFO: Added {len(new_lines) - len(old_lines)} lines')
else:
    print('✓ Line counts are comparable')
