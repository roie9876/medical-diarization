"""
Post-Processing Pipeline for Hebrew Medical Transcription

Stages:
A. Deterministic normalization (no LLM)
B. Dictionary spelling fixes (no LLM)
C. Deduplication (no LLM)
D. Semantic fix (constrained LLM)
E. Validation (no LLM)
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple, Optional, TYPE_CHECKING
from difflib import SequenceMatcher

if TYPE_CHECKING:
    from trace import PipelineTrace


# =============================================================================
# SPELLING DICTIONARY - Safe exact/near-exact replacements
# =============================================================================

SPELLING_FIXES = {
    # Common GPT-Audio Hebrew errors
    "עזות": "הזעות",
    "עקומול": "אקמול",
    "לעקומול": "לאקמול",
    "תחילות": "בחילות",
    "הרמונית": "ערמונית",
    "ההרמונית": "הערמונית",
    "מייחה": "ליחה",
    "מערך העצם": "מח העצם",
    "במערך העצם": "במח העצם",
    "ממערך העצם": "ממח העצם",
    "מהעצם": "ממח העצם",
    "פרוטיק": "פרטי",
    "בפרוטיק": "בפרטי",
    "העתק עדבק": "העתק הדבק",
    "כהי מים": "כולי מים",
    "כואי מים": "כולי מים",
    "הסמינים": "הסימפטומים",
    "במקריב": "בערב",
    "יציאה תקינות": "יציאות תקינות",
    "בליסה": "בלעיסה",
    "בכום הלב": "בקרום הלב",
    "רגישה יותר בנוח": "מרגישה יותר בנוח",
    "בנועל": "בנוהל",
    "קרדיולוק": "קרדילול",
    "חומס": "חום",
    "המסתרמות": "המסתמיות",
    "שאירו": "שלנו",
    "לדיין": "לדון",
    "חטפם": "התקף",
    # Medical term normalizations (to English)
    "אולטרסאונד": "Ultrasound",
    "מולטאק": "Multaq",
}

# Medical terms that should NEVER be modified
PROTECTED_MEDICAL_TERMS = {
    "DVT", "PE", "CT", "PET-CT", "PET CT", "TEE", "MRI", "ECG", "EKG",
    "IgG4", "IGG4", "Ultrasound", "Multaq", "Euthyrox", "Lipitor",
    "אנדוקרדיטיס", "סרקואיד", "לימפומה", "גרנולומות", "ביופסיה",
    "סטרואידים", "אימורן", "דיגוקסין", "פרוקור", "קרדילול",
}

# Valid speaker tags
VALID_SPEAKERS = {"[רופא]", "[מטופל]", "[בן משפחה]"}


@dataclass
class PostProcessReport:
    """Audit trail for post-processing"""
    stage_a_changes: List[str] = field(default_factory=list)
    stage_b_replacements: List[Tuple[str, str, int]] = field(default_factory=list)  # (old, new, line)
    stage_c_duplicates_removed: int = 0
    stage_c_duplicate_lines: List[int] = field(default_factory=list)
    stage_d_corrections: List[Tuple[int, str]] = field(default_factory=list)  # (line, reason)
    stage_e_warnings: List[str] = field(default_factory=list)
    stage_e_numbers_before: List[str] = field(default_factory=list)
    stage_e_numbers_after: List[str] = field(default_factory=list)
    stage_e_medical_terms_before: Set[str] = field(default_factory=set)
    stage_e_medical_terms_after: Set[str] = field(default_factory=set)
    validation_passed: bool = True


class PostProcessor:
    """Post-processing pipeline for Hebrew medical transcription"""
    
    def __init__(self, gpt52_client=None):
        self.gpt52_client = gpt52_client
        self.report = PostProcessReport()
    
    def process(
        self,
        text: str,
        use_llm: bool = True,
        trace: Optional["PipelineTrace"] = None,
    ) -> Tuple[str, PostProcessReport]:
        """
        Run the full post-processing pipeline
        
        Args:
            text: Raw merged transcription
            use_llm: Whether to use LLM for stage D (default True)
            trace: Optional PipelineTrace to record intermediate states
        
        Returns:
            Tuple of (processed_text, report)
        """
        self.report = PostProcessReport()
        
        # Extract numbers and medical terms BEFORE processing
        self.report.stage_e_numbers_before = self._extract_numbers(text)
        self.report.stage_e_medical_terms_before = self._extract_medical_terms(text)
        
        # Stage A: Deterministic normalization
        if trace:
            trace.start_timer("step_5a_normalized")
        text = self._stage_a_normalize(text)
        if trace:
            trace.add_step("step_5a_normalized", text)
        
        # Stage B: Dictionary spelling fixes
        if trace:
            trace.start_timer("step_5b_spelling")
        text = self._stage_b_spelling(text)
        if trace:
            trace.add_step("step_5b_spelling", text)
        
        # Stage C: Deduplication
        if trace:
            trace.start_timer("step_5c_deduplicated")
        text = self._stage_c_deduplicate(text)
        if trace:
            trace.add_step("step_5c_deduplicated", text)
        
        # Stage D: Semantic fix (LLM)
        if use_llm and self.gpt52_client:
            if trace:
                trace.start_timer("step_5d_semantic")
            text = self._stage_d_semantic_fix(text)
            if trace:
                trace.add_step("step_5d_semantic", text)
        
        # Stage E: Validation
        if trace:
            trace.start_timer("step_5e_validated")
        text = self._stage_e_validate(text)
        if trace:
            trace.add_step("step_5e_validated", text)
        
        return text, self.report
    
    # =========================================================================
    # STAGE A: Deterministic Normalization
    # =========================================================================
    
    def _stage_a_normalize(self, text: str) -> str:
        """Normalize whitespace, punctuation, and speaker tags"""
        lines = text.split('\n')
        normalized_lines = []
        
        for i, line in enumerate(lines):
            original = line
            
            # Skip empty lines
            if not line.strip():
                continue
            
            # Normalize whitespace
            line = ' '.join(line.split())
            
            # Fix speaker tag formatting
            line = self._normalize_speaker_tag(line)
            
            # Normalize punctuation
            line = self._normalize_punctuation(line)
            
            # Normalize medical term formatting
            line = self._normalize_medical_terms(line)
            
            if line != original:
                self.report.stage_a_changes.append(f"Line {i+1}: normalized")
            
            normalized_lines.append(line)
        
        return '\n'.join(normalized_lines)
    
    def _normalize_speaker_tag(self, line: str) -> str:
        """Ensure line starts with valid speaker tag"""
        # Check if line already has a valid tag
        for tag in VALID_SPEAKERS:
            if line.startswith(tag):
                # Ensure colon after tag
                rest = line[len(tag):].lstrip()
                if not rest.startswith(':'):
                    rest = ': ' + rest
                elif rest.startswith(':'):
                    rest = ': ' + rest[1:].lstrip()
                return tag + rest
        
        # Try to fix common tag errors
        tag_fixes = {
            "[קופא]": "[רופא]",
            "[רופאה]": "[רופא]",
            "[חולה]": "[מטופל]",
            "[משפחה]": "[בן משפחה]",
        }
        
        for wrong, correct in tag_fixes.items():
            if line.startswith(wrong):
                return correct + line[len(wrong):]
        
        return line
    
    def _normalize_punctuation(self, line: str) -> str:
        """Normalize Hebrew punctuation"""
        # Fix multiple spaces after colon
        line = re.sub(r':\s+', ': ', line)
        
        # Fix multiple question marks
        line = re.sub(r'\?+', '?', line)
        
        # Remove trailing whitespace
        line = line.rstrip()
        
        return line
    
    def _normalize_medical_terms(self, line: str) -> str:
        """Standardize medical term formatting"""
        # PET CT -> PET-CT
        line = re.sub(r'\bPET\s+CT\b', 'PET-CT', line)
        
        # Ensure consistent capitalization for known terms
        term_map = {
            'pet-ct': 'PET-CT',
            'tee': 'TEE',
            'dvt': 'DVT',
            'igg4': 'IgG4',
        }
        
        for lower, proper in term_map.items():
            line = re.sub(rf'\b{lower}\b', proper, line, flags=re.IGNORECASE)
        
        return line
    
    # =========================================================================
    # STAGE B: Dictionary Spelling Fixes
    # =========================================================================
    
    def _stage_b_spelling(self, text: str) -> str:
        """Apply safe dictionary-based spelling corrections"""
        lines = text.split('\n')
        fixed_lines = []
        
        for i, line in enumerate(lines):
            original = line
            
            # Apply each fix
            for wrong, correct in SPELLING_FIXES.items():
                if wrong in line:
                    # Don't fix inside English medical terms
                    if not self._is_inside_medical_term(line, wrong):
                        line = line.replace(wrong, correct)
                        self.report.stage_b_replacements.append((wrong, correct, i+1))
            
            fixed_lines.append(line)
        
        return '\n'.join(fixed_lines)
    
    def _is_inside_medical_term(self, line: str, word: str) -> bool:
        """Check if word appears inside a protected medical term"""
        for term in PROTECTED_MEDICAL_TERMS:
            if word in term and term in line:
                return True
        return False
    
    # =========================================================================
    # STAGE C: Deduplication
    # =========================================================================
    
    def _stage_c_deduplicate(self, text: str) -> str:
        """Remove duplicate paragraphs and sentences"""
        lines = text.split('\n')
        
        # First pass: remove exact duplicate consecutive lines
        deduped = []
        prev_fingerprint = None
        
        for i, line in enumerate(lines):
            fingerprint = self._get_fingerprint(line)
            
            if fingerprint == prev_fingerprint and fingerprint:
                self.report.stage_c_duplicates_removed += 1
                self.report.stage_c_duplicate_lines.append(i+1)
                continue
            
            prev_fingerprint = fingerprint
            deduped.append(line)
        
        # Second pass: remove near-duplicate blocks (window of 1-4 lines)
        deduped = self._remove_near_duplicate_blocks(deduped)
        
        return '\n'.join(deduped)
    
    def _get_fingerprint(self, line: str) -> str:
        """Create normalized fingerprint for comparison"""
        if not line.strip():
            return ""
        
        # Remove speaker tag
        for tag in VALID_SPEAKERS:
            if line.startswith(tag):
                line = line[len(tag):]
                break
        
        # Normalize
        line = line.lower()
        line = re.sub(r'[^\w\s]', '', line)  # Remove punctuation
        line = ' '.join(line.split())  # Normalize whitespace
        
        # Normalize Hebrew final letters
        finals = {'ך': 'כ', 'ם': 'מ', 'ן': 'נ', 'ף': 'פ', 'ץ': 'צ'}
        for final, regular in finals.items():
            line = line.replace(final, regular)
        
        return line
    
    def _remove_near_duplicate_blocks(self, lines: List[str]) -> List[str]:
        """Remove blocks that are near-duplicates of earlier blocks"""
        if len(lines) < 4:
            return lines
        
        result = []
        i = 0
        
        while i < len(lines):
            # Get current block (1-4 lines)
            current_block = []
            for j in range(min(4, len(lines) - i)):
                if lines[i + j].strip():
                    current_block.append(self._get_fingerprint(lines[i + j]))
            
            if not current_block:
                result.append(lines[i])
                i += 1
                continue
            
            # Check if this block appeared before in result
            is_duplicate = False
            block_text = ' '.join(current_block)
            
            # Look back in result for similar block
            for k in range(max(0, len(result) - 20), len(result)):
                # Build comparison block from result
                compare_block = []
                for j in range(min(4, len(result) - k)):
                    if result[k + j].strip():
                        compare_block.append(self._get_fingerprint(result[k + j]))
                
                compare_text = ' '.join(compare_block)
                
                # Check similarity
                if block_text and compare_text:
                    similarity = SequenceMatcher(None, block_text, compare_text).ratio()
                    if similarity > 0.85:
                        is_duplicate = True
                        self.report.stage_c_duplicates_removed += 1
                        self.report.stage_c_duplicate_lines.append(i + 1)
                        break
            
            if not is_duplicate:
                result.append(lines[i])
            
            i += 1
        
        return result
    
    # =========================================================================
    # STAGE D: Semantic Fix (Constrained LLM)
    # =========================================================================
    
    def _stage_d_semantic_fix(self, text: str) -> str:
        """Use LLM for safe semantic corrections only"""
        
        if not self.gpt52_client:
            return text
        
        # Extract medical terms and numbers that MUST be preserved
        numbers = self._extract_numbers(text)
        medical_terms = self._extract_medical_terms(text)
        
        prompt = f"""תקן שגיאות דקדוק ותחביר בעברית בתמלול הרפואי הבא.

כללים קריטיים - חובה לציית:
1. אסור לשנות מספרים: {', '.join(numbers[:20])}... (שמור את כולם בדיוק)
2. אסור להחליף מונחים רפואיים: {', '.join(list(medical_terms)[:15])}...
3. אסור להמציא אבחנות, בדיקות, או תרופות חדשות
4. שמור על סימוני הדוברים בדיוק: [רופא], [מטופל], [בן משפחה]
5. אל תקצר את הטקסט - שמור על כל המשפטים

מה מותר לתקן:
- שגיאות דקדוק בעברית (זכר/נקבה, יחיד/רבים)
- מילים שבורות או חתוכות
- סדר מילים לא תקין במשפט

אם אתה לא בטוח - השאר את המקור!

הטקסט:
{text}

החזר את הטקסט המתוקן בלבד:"""

        try:
            completion = self.gpt52_client.chat.completions.create(
                model="gpt-5.2-chat",
                messages=[{"role": "user", "content": prompt}],
                max_completion_tokens=32000,
            )
            
            result = completion.choices[0].message.content
            
            # Safety check: don't accept if too short
            if len(result) < len(text) * 0.9:
                self.report.stage_d_corrections.append((0, "LLM result too short, keeping original"))
                return text
            
            return result
            
        except Exception as e:
            self.report.stage_d_corrections.append((0, f"LLM error: {str(e)}"))
            return text
    
    # =========================================================================
    # STAGE E: Validation
    # =========================================================================
    
    def _stage_e_validate(self, text: str) -> str:
        """Validate the processed text and flag issues"""
        
        # Extract numbers and medical terms AFTER processing
        self.report.stage_e_numbers_after = self._extract_numbers(text)
        self.report.stage_e_medical_terms_after = self._extract_medical_terms(text)
        
        # Check 1: Numbers preserved
        numbers_before = set(self.report.stage_e_numbers_before)
        numbers_after = set(self.report.stage_e_numbers_after)
        
        missing_numbers = numbers_before - numbers_after
        if missing_numbers:
            self.report.stage_e_warnings.append(
                f"Numbers changed/missing: {missing_numbers}"
            )
            self.report.validation_passed = False
        
        # Check 2: Medical terms preserved
        terms_before = self.report.stage_e_medical_terms_before
        terms_after = self.report.stage_e_medical_terms_after
        
        missing_terms = terms_before - terms_after
        if missing_terms:
            self.report.stage_e_warnings.append(
                f"Medical terms missing: {missing_terms}"
            )
            self.report.validation_passed = False
        
        # Check 3: New medical terms introduced (hallucination?)
        new_terms = terms_after - terms_before
        # Filter out terms that are just case variations
        real_new_terms = {t for t in new_terms 
                         if t.lower() not in {x.lower() for x in terms_before}}
        # Filter out terms that came from spelling dictionary
        spelling_targets = set(SPELLING_FIXES.values())
        real_new_terms = {t for t in real_new_terms if t not in spelling_targets}
        
        if real_new_terms:
            self.report.stage_e_warnings.append(
                f"New medical terms introduced (possible hallucination): {real_new_terms}"
            )
        
        # Check 4: Speaker tag sanity
        lines = text.split('\n')
        speaker_counts = {"[רופא]": 0, "[מטופל]": 0, "[בן משפחה]": 0}
        lines_without_speaker = 0
        
        for line in lines:
            if not line.strip():
                continue
            
            has_speaker = False
            for tag in VALID_SPEAKERS:
                if line.startswith(tag):
                    speaker_counts[tag] += 1
                    has_speaker = True
                    break
            
            if not has_speaker and line.strip():
                lines_without_speaker += 1
        
        if lines_without_speaker > 5:
            self.report.stage_e_warnings.append(
                f"{lines_without_speaker} lines without speaker tags"
            )
        
        total_lines = sum(speaker_counts.values())
        if total_lines > 0:
            # Check for extreme imbalance
            for tag, count in speaker_counts.items():
                if count / total_lines > 0.9:
                    self.report.stage_e_warnings.append(
                        f"Speaker imbalance: {tag} has {count}/{total_lines} lines ({100*count/total_lines:.0f}%)"
                    )
        
        return text
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def _extract_numbers(self, text: str) -> List[str]:
        """Extract all numbers from text"""
        # Match integers, decimals, percentages
        pattern = r'\b\d+(?:\.\d+)?%?\b'
        return re.findall(pattern, text)
    
    def _extract_medical_terms(self, text: str) -> Set[str]:
        """Extract medical terms from text"""
        terms = set()
        
        # English medical terms (2+ chars, uppercase or mixed)
        english_pattern = r'\b[A-Z][A-Za-z0-9-]{1,}\b'
        terms.update(re.findall(english_pattern, text))
        
        # Known Hebrew medical terms
        hebrew_medical = [
            "אנדוקרדיטיס", "סרקואיד", "לימפומה", "גרנולומות", "ביופסיה",
            "סטרואידים", "אימורן", "דיגוקסין", "פרוקור", "קרדילול",
            "טמפורלית", "המטולוגים", "ראומטולוגים", "קרדיולוגים",
            "מסתמים", "פירפור", "אשפוז",
        ]
        for term in hebrew_medical:
            if term in text:
                terms.add(term)
        
        return terms


def format_report(report: PostProcessReport) -> str:
    """Format the post-processing report for display"""
    lines = [
        "=" * 60,
        "POST-PROCESSING REPORT",
        "=" * 60,
        "",
        f"Stage A (Normalization): {len(report.stage_a_changes)} changes",
        f"Stage B (Spelling): {len(report.stage_b_replacements)} replacements",
        f"Stage C (Deduplication): {report.stage_c_duplicates_removed} duplicates removed",
        f"Stage D (Semantic): {len(report.stage_d_corrections)} corrections",
        "",
        f"Validation: {'✓ PASSED' if report.validation_passed else '✗ FAILED'}",
    ]
    
    if report.stage_e_warnings:
        lines.append("")
        lines.append("Warnings:")
        for warning in report.stage_e_warnings:
            lines.append(f"  ⚠️  {warning}")
    
    if report.stage_b_replacements:
        lines.append("")
        lines.append("Spelling replacements:")
        for old, new, line_num in report.stage_b_replacements[:10]:
            lines.append(f"  Line {line_num}: '{old}' → '{new}'")
        if len(report.stage_b_replacements) > 10:
            lines.append(f"  ... and {len(report.stage_b_replacements) - 10} more")
    
    lines.append("=" * 60)
    
    return '\n'.join(lines)
