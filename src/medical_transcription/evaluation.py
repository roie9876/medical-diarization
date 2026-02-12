"""
Evaluation metrics for comparing transcriptions
"""

import re
from difflib import SequenceMatcher
from typing import Dict, List, Tuple


def normalize_text(text: str) -> str:
    """Normalize text for comparison"""
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    # Normalize speaker labels
    text = re.sub(r'\[דובר\s*(\d+)\]', r'[Speaker \1]', text)
    text = re.sub(r'\[Speaker\s*(\d+)\s*\]', r'[Speaker \1]', text)
    # Remove trailing/leading whitespace
    text = text.strip()
    return text


def extract_speakers(text: str) -> Dict[str, List[str]]:
    """Extract utterances per speaker"""
    speakers = {}
    # Match both Hebrew and English speaker labels
    pattern = r'\[(Speaker \d+|דובר \d+)\]:\s*(.+?)(?=\[(?:Speaker|דובר) \d+\]|$)'
    matches = re.findall(pattern, text, re.DOTALL)
    
    for speaker, utterance in matches:
        speaker = re.sub(r'דובר', 'Speaker', speaker)
        if speaker not in speakers:
            speakers[speaker] = []
        speakers[speaker].append(utterance.strip())
    
    return speakers


def character_accuracy(reference: str, hypothesis: str) -> float:
    """
    Calculate character-level accuracy using SequenceMatcher
    Returns value between 0 and 1
    """
    ref_norm = normalize_text(reference)
    hyp_norm = normalize_text(hypothesis)
    
    matcher = SequenceMatcher(None, ref_norm, hyp_norm)
    return matcher.ratio()


def word_error_rate(reference: str, hypothesis: str) -> float:
    """
    Calculate Word Error Rate (WER)
    Lower is better. 0 = perfect match
    """
    ref_words = normalize_text(reference).split()
    hyp_words = normalize_text(hypothesis).split()
    
    # Dynamic programming for edit distance
    d = [[0] * (len(hyp_words) + 1) for _ in range(len(ref_words) + 1)]
    
    for i in range(len(ref_words) + 1):
        d[i][0] = i
    for j in range(len(hyp_words) + 1):
        d[0][j] = j
    
    for i in range(1, len(ref_words) + 1):
        for j in range(1, len(hyp_words) + 1):
            if ref_words[i-1] == hyp_words[j-1]:
                d[i][j] = d[i-1][j-1]
            else:
                d[i][j] = min(
                    d[i-1][j] + 1,    # deletion
                    d[i][j-1] + 1,    # insertion
                    d[i-1][j-1] + 1   # substitution
                )
    
    if len(ref_words) == 0:
        return 1.0 if len(hyp_words) > 0 else 0.0
    
    return d[len(ref_words)][len(hyp_words)] / len(ref_words)


def medical_term_accuracy(reference: str, hypothesis: str) -> Dict[str, any]:
    """
    Check if medical terms are correctly transcribed in English
    """
    # Common medical terms to look for
    medical_terms = [
        'DVT', 'PE', 'Ultrasound', 'CT', 'MRI', 'ECG', 'EKG',
        'Euthyrox', 'Eltroxin', 'Aspirin', 'Warfarin', 'Lipitor',
        'Blood pressure', 'Cholesterol', 'Diabetes', 'Hypertension',
        'X-ray', 'Blood test'
    ]
    
    ref_lower = reference.lower()
    hyp_lower = hypothesis.lower()
    
    found_in_ref = []
    found_in_hyp = []
    
    for term in medical_terms:
        if term.lower() in ref_lower:
            found_in_ref.append(term)
        if term.lower() in hyp_lower:
            found_in_hyp.append(term)
    
    # Check Hebrew equivalents that should have been converted
    hebrew_medical = {
        'אולטרסאונד': 'Ultrasound',
        'יוטירוקס': 'Euthyrox',
        'אלטרוקסין': 'Eltroxin',
        'לחץ דם': 'Blood pressure',
        'כולסטרול': 'Cholesterol',
        'סוכרת': 'Diabetes',
    }
    
    unconverted = []
    for heb, eng in hebrew_medical.items():
        if heb in hypothesis and eng.lower() not in hyp_lower:
            unconverted.append(f"{heb} should be {eng}")
    
    return {
        "terms_in_reference": found_in_ref,
        "terms_in_hypothesis": found_in_hyp,
        "unconverted_hebrew": unconverted,
        "english_term_count": len(found_in_hyp),
    }


def speaker_diarization_accuracy(reference: str, hypothesis: str) -> Dict[str, any]:
    """
    Evaluate speaker diarization accuracy
    """
    ref_speakers = extract_speakers(reference)
    hyp_speakers = extract_speakers(hypothesis)
    
    ref_count = len(ref_speakers)
    hyp_count = len(hyp_speakers)
    
    ref_turns = sum(len(v) for v in ref_speakers.values())
    hyp_turns = sum(len(v) for v in hyp_speakers.values())
    
    return {
        "reference_speakers": ref_count,
        "hypothesis_speakers": hyp_count,
        "speaker_count_match": ref_count == hyp_count,
        "reference_turns": ref_turns,
        "hypothesis_turns": hyp_turns,
    }


def calculate_all_metrics(reference: str, hypothesis: str) -> Dict[str, any]:
    """
    Calculate all evaluation metrics
    """
    char_acc = character_accuracy(reference, hypothesis)
    wer = word_error_rate(reference, hypothesis)
    medical = medical_term_accuracy(reference, hypothesis)
    diarization = speaker_diarization_accuracy(reference, hypothesis)
    
    # Combined score (weighted)
    # Higher is better
    combined_score = (
        char_acc * 0.4 +                              # 40% character accuracy
        (1 - min(wer, 1.0)) * 0.4 +                   # 40% word accuracy (inverted WER)
        (1 if diarization["speaker_count_match"] else 0.5) * 0.1 +  # 10% speaker match
        min(medical["english_term_count"] / 5, 1.0) * 0.1  # 10% medical terms
    )
    
    return {
        "character_accuracy": round(char_acc, 4),
        "word_error_rate": round(wer, 4),
        "word_accuracy": round(1 - min(wer, 1.0), 4),
        "medical_terms": medical,
        "diarization": diarization,
        "combined_score": round(combined_score, 4),
    }


def format_metrics_report(metrics: Dict) -> str:
    """Format metrics as a readable report"""
    report = []
    report.append("=" * 60)
    report.append("EVALUATION METRICS")
    report.append("=" * 60)
    report.append(f"Combined Score:      {metrics['combined_score']:.2%}")
    report.append(f"Character Accuracy:  {metrics['character_accuracy']:.2%}")
    report.append(f"Word Accuracy:       {metrics['word_accuracy']:.2%}")
    report.append(f"Word Error Rate:     {metrics['word_error_rate']:.2%}")
    report.append("-" * 60)
    report.append("Speaker Diarization:")
    report.append(f"  Reference speakers: {metrics['diarization']['reference_speakers']}")
    report.append(f"  Hypothesis speakers: {metrics['diarization']['hypothesis_speakers']}")
    report.append(f"  Match: {'✓' if metrics['diarization']['speaker_count_match'] else '✗'}")
    report.append("-" * 60)
    report.append("Medical Terms:")
    report.append(f"  Found in output: {metrics['medical_terms']['terms_in_hypothesis']}")
    if metrics['medical_terms']['unconverted_hebrew']:
        report.append(f"  Unconverted Hebrew: {metrics['medical_terms']['unconverted_hebrew']}")
    report.append("=" * 60)
    
    return "\n".join(report)
