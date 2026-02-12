#!/usr/bin/env python3
"""
Variance Test - Run multiple transcriptions to measure consistency
"""
import os
import sys
import json
import re
from datetime import datetime

# Project root & source path setup
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src", "medical_transcription"))
from transcribe import MedicalTranscriber

# Test configuration
NUM_RUNS = 3  # Number of test runs
SAMPLE_PATH = os.path.join(PROJECT_ROOT, "samples", "sample2", "audio.mp3")
OUTPUT_BASE = os.path.join(PROJECT_ROOT, "output", "variance_test")

# Key medical data points to track
MEDICAL_NUMBERS = [
    (r'37\.?\d*', 'temperature_low'),
    (r'38\.?\d*', 'temperature_high'),
    (r'43', 'age'),
    (r'2020', 'year_hospitalized'),
    (r'DVT', 'diagnosis_dvt'),
    (r'Lipitor|ליפיטור', 'medication_lipitor'),
    (r'Euthyrox|אותירוקס', 'medication_euthyrox'),
    (r'Ultrasound|אולטרסאונד', 'test_ultrasound'),
    (r'שבוע וחצי', 'duration_symptoms'),
    (r'כירורג|חירורג', 'surgeon'),
    (r'פקקת', 'clot'),
]

def extract_medical_data(text):
    """Extract key medical data points from transcription"""
    data = {}
    for pattern, key in MEDICAL_NUMBERS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        data[key] = matches if matches else None
    
    # Count speakers
    data['speaker_doctor'] = text.count('[רופא]')
    data['speaker_patient'] = text.count('[מטופל]')
    data['speaker_family'] = text.count('[בן משפחה]')
    
    # Total length
    data['total_chars'] = len(text)
    data['total_lines'] = len(text.splitlines())
    
    return data

def compare_runs(results):
    """Compare medical data across all runs"""
    print("\n" + "="*70)
    print("VARIANCE ANALYSIS")
    print("="*70)
    
    # Get all keys from first result
    all_keys = list(results[0]['medical_data'].keys())
    
    print(f"\n{'Data Point':<25} | " + " | ".join([f"Run {i+1:<5}" for i in range(len(results))]) + " | Status")
    print("-"*100)
    
    consistent_count = 0
    inconsistent_count = 0
    
    for key in all_keys:
        values = [r['medical_data'].get(key) for r in results]
        
        # Check if all values are the same
        if all(v == values[0] for v in values):
            status = "✓ CONSISTENT"
            consistent_count += 1
        else:
            status = "⚠️ VARIES"
            inconsistent_count += 1
        
        # Format values for display
        formatted_values = []
        for v in values:
            if isinstance(v, list):
                formatted_values.append(str(v)[:20])
            elif isinstance(v, int):
                formatted_values.append(str(v))
            else:
                formatted_values.append(str(v)[:20] if v else "None")
        
        print(f"{key:<25} | " + " | ".join([f"{v:<7}" for v in formatted_values]) + f" | {status}")
    
    print("-"*100)
    print(f"\nSUMMARY:")
    print(f"  Consistent data points: {consistent_count}/{len(all_keys)}")
    print(f"  Variable data points:   {inconsistent_count}/{len(all_keys)}")
    print(f"  Consistency rate:       {consistent_count/len(all_keys)*100:.1f}%")
    
    # Length variance
    lengths = [r['medical_data']['total_chars'] for r in results]
    print(f"\n  Output length variance:")
    print(f"    Min: {min(lengths):,} chars")
    print(f"    Max: {max(lengths):,} chars")
    print(f"    Diff: {max(lengths) - min(lengths):,} chars ({(max(lengths)-min(lengths))/min(lengths)*100:.1f}%)")
    
    return consistent_count, inconsistent_count


def main():
    print("="*70)
    print("VARIANCE TEST - Measuring Transcription Consistency")
    print("="*70)
    print(f"\nConfiguration:")
    print(f"  Number of runs: {NUM_RUNS}")
    print(f"  Audio file: {SAMPLE_PATH}")
    print(f"  Medical data points tracked: {len(MEDICAL_NUMBERS)}")
    
    # Create output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(OUTPUT_BASE, timestamp)
    os.makedirs(output_dir, exist_ok=True)
    
    # Initialize transcriber
    transcriber = MedicalTranscriber()
    
    results = []
    
    for run_num in range(1, NUM_RUNS + 1):
        print(f"\n{'='*70}")
        print(f"RUN {run_num}/{NUM_RUNS}")
        print(f"{'='*70}")
        
        run_output_dir = os.path.join(output_dir, f"run_{run_num:02d}")
        
        start_time = datetime.now()
        result = transcriber.transcribe(
            audio_path=SAMPLE_PATH,
            output_dir=run_output_dir
        )
        end_time = datetime.now()
        
        # Extract medical data
        medical_data = extract_medical_data(result['final_transcription'])
        
        results.append({
            'run_num': run_num,
            'processing_time': (end_time - start_time).total_seconds(),
            'transcription': result['final_transcription'],
            'medical_data': medical_data
        })
        
        print(f"\n  Run {run_num} completed: {medical_data['total_chars']:,} chars in {results[-1]['processing_time']:.1f}s")
    
    # Compare all runs
    consistent, inconsistent = compare_runs(results)
    
    # Save detailed comparison
    comparison_file = os.path.join(output_dir, "comparison_report.json")
    with open(comparison_file, 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': timestamp,
            'num_runs': NUM_RUNS,
            'sample': SAMPLE_PATH,
            'results': [
                {
                    'run': r['run_num'],
                    'time': r['processing_time'],
                    'chars': r['medical_data']['total_chars'],
                    'lines': r['medical_data']['total_lines'],
                }
                for r in results
            ],
            'consistent_points': consistent,
            'inconsistent_points': inconsistent,
            'consistency_rate': consistent / (consistent + inconsistent) * 100
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Results saved to: {output_dir}")
    print(f"   Comparison report: {comparison_file}")
    
    # Print specific text comparison for the fever line
    print("\n" + "="*70)
    print("SPECIFIC TEXT COMPARISON - 'חום קבוע' line")
    print("="*70)
    for r in results:
        lines = r['transcription'].splitlines()
        for line in lines:
            if 'חום קבוע' in line or 'חום' in line[:50]:
                print(f"\nRun {r['run_num']}:")
                print(f"  {line[:150]}...")
                break


if __name__ == "__main__":
    main()
