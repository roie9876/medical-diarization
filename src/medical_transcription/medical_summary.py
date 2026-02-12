"""
Medical Summary Generator — Step 6 of the Pipeline

Takes the final post-processed transcription and produces a structured
Hebrew medical summary.

Critical safety guards:
1. No hallucinated medications — only meds explicitly in the transcript
2. No fabricated information — "לא צוין" for missing data, never invent
3. Duplicate medication detection — brand-name / generic-name equivalences
4. Dosage plausibility — flag suspicious dosages
5. Chief complaint accuracy — not biased toward last topic discussed
6. Background medical history — only from the transcript, nothing invented
"""

import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from trace import PipelineTrace


# ─────────────────────────────────────────────────────────────────────────────
# Known brand / generic equivalences (Hebrew + English mixed as they appear)
# Each tuple group represents the SAME drug.
# ─────────────────────────────────────────────────────────────────────────────

MEDICATION_EQUIVALENCES: List[Set[str]] = [
    # ACE Inhibitors
    {"Ramipril", "Tritace", "רמיפריל", "טריטייס", "טרייטייס"},
    {"Enalapril", "Renitec", "אנלפריל", "רניטק"},
    # Beta Blockers
    {"Cardiloc", "Bisoprolol", "קרדילוק", "ביסופרולול"},
    {"Nebivolol", "Nebilet", "נביוולול", "נבילט"},
    # Statins
    {"Lipitor", "Atorvastatin", "ליפיטור", "אטורבסטטין"},
    {"Crestor", "Rosuvastatin", "קרסטור", "רוזובסטטין"},
    {"Simvastatin", "Simvacor", "סימבסטטין", "סימבקור"},
    # Cholesterol absorption
    {"Ezetrol", "Ezetimibe", "אזטרול", "אזטימיב"},
    {"Timibe", "Ezetimibe", "טימיב", "אזטימיב"},  # Timibe = brand of Ezetimibe
    # Ezetimibe+Statin combos
    {"Inegy", "Ezetimibe/Simvastatin", "אניגי"},
    # ARBs
    {"Losartan", "Ocsaar", "לוסרטן", "אוקסאר"},
    {"Valsartan", "Diovan", "ולסרטן", "דיובן"},
    # Diuretics
    {"Spironolactone", "Aldactone", "ספירונולקטון", "אלדקטון"},
    {"Furosemide", "Fusid", "Lasix", "פורוסמיד", "פיוסיד", "לסיקס"},
    # Anticoagulants
    {"Eliquis", "Apixaban", "אליקוויס", "אפיקסבן"},
    {"Xarelto", "Rivaroxaban", "קסרלטו", "ריברוקסבן"},
    {"Pradaxa", "Dabigatran", "פרדקסה", "דביגטרן"},
    # Antiplatelets
    {"Aspirin Cardio", "Aspirin", "Micropirin", "אספירין", "מיקרופירין", "אספירין קרדיו", "קרדיו אספירין"},
    {"Effient", "Prasugrel", "אפיינט", "פרזוגרל"},
    {"Plavix", "Clopidogrel", "פלוויקס", "קלופידוגרל"},
    # Diabetes
    {"Metformin", "Glucophage", "Glucomin", "מטפורמין", "גלוקופאג'", "גלוקומין"},
    {"Jardiance", "Empagliflozin", "ג'רדיאנס", "אמפגליפלוזין"},
    {"Ozempic", "Semaglutide", "אוזמפיק", "סמגלוטייד"},
    {"Trulicity", "Dulaglutide", "טרוליסיטי", "דולגלוטייד"},
    # PPI
    {"Nexium", "Esomeprazole", "נקסיום", "אסומפרזול"},
    {"Omeprazole", "Losec", "Omepradex", "אומפרזול", "לוסק", "אומפרדקס"},
    {"Opodix", "Dexlansoprazole", "אופודיקס"},
    # Sleep
    {"Zopiclone", "Nocturno", "Imovane", "זופיקלון", "נוקטורנו", "אימובן"},
    # Antidepressants
    {"Cipralex", "Escitalopram", "ציפרלקס", "אסציטלופרם"},
    # Benzodiazepines
    {"Clonex", "Clonazepam", "קלונקס", "קלונזפם"},
    {"Lorivan", "Lorazepam", "לוריבן", "לורזפם"},
    # Thyroid
    {"Euthyrox", "Levothyroxine", "Eltroxin", "אותירוקס", "לבותירוקסין", "אלטרוקסין"},
    # Antiarrhythmics
    {"Multaq", "Dronedarone", "מולטאק", "דרונדרון"},
]

# Build fast lookup: normalized_name → set_index
_MED_LOOKUP: Dict[str, int] = {}
for _idx, _group in enumerate(MEDICATION_EQUIVALENCES):
    for _name in _group:
        _MED_LOOKUP[_name.lower()] = _idx
        _MED_LOOKUP[_name.lower().replace("-", "")] = _idx
        _MED_LOOKUP[_name.lower().replace("'", "")] = _idx


# ─────────────────────────────────────────────────────────────────────────────
# Known dosage ranges (mg) — for plausibility checks
# Format: drug_group_index → (min_single_dose_mg, max_single_dose_mg)
# These are approximate clinical ranges; outliers get flagged, not blocked.
# ─────────────────────────────────────────────────────────────────────────────

DOSAGE_RANGES: Dict[str, Tuple[float, float]] = {
    "ramipril": (1.25, 10),
    "tritace": (1.25, 10),
    "bisoprolol": (1.25, 10),
    "cardiloc": (1.25, 10),
    "enalapril": (2.5, 40),
    "losartan": (25, 100),
    "valsartan": (40, 320),
    "atorvastatin": (10, 80),
    "lipitor": (10, 80),
    "rosuvastatin": (5, 40),
    "crestor": (5, 40),
    "simvastatin": (5, 80),
    "ezetimibe": (10, 10),
    "ezetrol": (10, 10),
    "spironolactone": (12.5, 200),
    "aldactone": (12.5, 200),
    "furosemide": (20, 600),
    "aspirin": (75, 325),
    "prasugrel": (5, 10),
    "effient": (5, 10),
    "clopidogrel": (75, 75),
    "plavix": (75, 75),
    "apixaban": (2.5, 5),
    "eliquis": (2.5, 5),
    "rivaroxaban": (10, 20),
    "xarelto": (10, 20),
    "metformin": (500, 2550),
    "glucophage": (500, 2550),
    "empagliflozin": (10, 25),
    "jardiance": (10, 25),
    "zopiclone": (3.75, 7.5),
    "nocturno": (3.75, 7.5),
    "escitalopram": (5, 20),
    "cipralex": (5, 20),
    "clonazepam": (0.25, 6),
    "clonex": (0.25, 6),
    "lorazepam": (0.5, 6),
    "lorivan": (0.5, 6),
    "omeprazole": (10, 40),
    "esomeprazole": (20, 40),
    "nexium": (20, 40),
    "levothyroxine": (12.5, 300),
    "euthyrox": (12.5, 300),
    "eltroxin": (12.5, 300),
}


# ─────────────────────────────────────────────────────────────────────────────
# Summary template — the target structured output
# ─────────────────────────────────────────────────────────────────────────────

SUMMARY_TEMPLATE = """
---רקע דמוגרפי---

• גיל:
• מין:
• מצב משפחתי:
• מגורים:
• עיסוק:

---רקע רפואי---

• מחלות ברקע:
• תרופות כרוניות:
• אלרגיות:

---תלונה עיקרית---

---פרטי המחלה הנוכחית---

---בדיקה גופנית---

---תוצאות מעבדה---

---דימות ובדיקות עזר---

---סיכום רפואי של הרופא---

---המלצות---

---מרשמים---
""".strip()


# ─────────────────────────────────────────────────────────────────────────────
# LLM system prompt — extremely detailed to prevent hallucinations
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """אתה מערכת לסיכום רפואי מדויק. תפקידך להפיק סיכום רפואי מובנה מתמלול שיחה בין רופא למטופל.

## כללי ברזל — חובה לעקוב אחריהם:

### 1. אסור בתכלית האיסור להמציא מידע
- כתוב **רק** מידע שנאמר במפורש בתמלול.
- אם מידע חסר (למשל: גיל, בדיקה גופנית, אלרגיות) — כתוב **"לא צוין"**.
- אל תסיק, אל תניח, אל תוסיף פרטים שלא הוזכרו בתמלול.
- זה חל גם על מחלות רקע, תרופות, תוצאות בדיקות — הכל חייב להיות מבוסס על התמלול בלבד.

### 2. תרופות — דיוק מוחלט
- רשום **רק** תרופות שהוזכרו במפורש בתמלול.
- **אסור** להוסיף תרופות שלא נאמרו, גם אם הן "הגיוניות" לפי האבחנה.
- אם שם תרופה לא ברור בתמלול, רשום אותו כפי שנשמע עם סימן שאלה: "בטרן (?)".
- **אסור** לרשום את אותה תרופה פעמיים בשמות שונים. למשל, אם בתמלול נאמר גם "Ramipril" וגם "Tritace" — אלו אותה תרופה! רשום רק אחת מהן וציין בסוגריים את השם החלופי: "Ramipril (Tritace)".

דוגמאות לכפילויות נפוצות שיש לאחד:
- Ramipril = Tritace (רמיפריל = טריטייס)
- Cardiloc = Bisoprolol (קרדילוק = ביסופרולול)
- Lipitor = Atorvastatin (ליפיטור = אטורבסטטין)
- Spironolactone = Aldactone (ספירונולקטון = אלדקטון)
- Zopiclone = Nocturno (זופיקלון = נוקטורנו)
- Ezetrol = Timibe = Ezetimibe (אזטרול = טימיב = אזטימיב)
- Aspirin Cardio = Aspirin = Micropirin
- Effient = Prasugrel (אפיינט = פרזוגרל)
- Metformin = Glucophage = Glucomin (מטפורמין = גלוקופאג = גלוקומין)
- Nexium = Esomeprazole (נקסיום = אסומפרזול)
- Ozempic = Semaglutide (אוזמפיק = סמגלוטייד)
- Eliquis = Apixaban (אליקוויס = אפיקסבן)

### 3. מינון — בדיקת סבירות
- אם מינון נאמר בתמלול, רשום אותו כפי שנאמר.
- אם המינון נשמע לא הגיוני מבחינה רפואית, הוסף הערה: "⚠️ ייתכן שגיאת תמלול — מינון חריג".
- למשל: "Ramipril 11.5 mg" — מינון כזה לא קיים. ציין: "Ramipril 11.5 mg ⚠️ ייתכן שגיאת תמלול — מינון לא סטנדרטי (טווח תקין: 1.25-10 mg)".
- אל תשנה את המינון בעצמך — רק סמן אזהרה.

### 4. תלונה עיקרית — לא להתבלבל עם הנושא האחרון
- התלונה העיקרית היא **הסיבה שבגללה המטופל הגיע** לרופא, לא הנושא האחרון שנדון.
- בדרך כלל היא מופיעה בתחילת השיחה כשהרופא שואל "למה הגעת?" או "מה מפריע?".
- אל תתבלבל בין התלונה העיקרית לבין דיונים צדדיים או נושאים שעלו בהמשך השיחה.

### 5. רקע רפואי ומחלות רקע
- רשום רק מחלות שהוזכרו בתמלול.
- אם לא הוזכרו מחלות רקע, כתוב "לא צוין".
- אסור להוסיף מחלות "הגיוניות" לפי התרופות (למשל, אם נוטל סטטין, אל תוסיף "היפרליפידמיה" אלא אם הוזכרה).

### 6. בדיקה גופנית
- רשום ממצאים רק אם הרופא תיאר אותם בתמלול.
- אם לא נעשתה בדיקה גופנית או שלא תוארה — כתוב "לא צוין".

### 7. מרשמים
- בקטגוריית "מרשמים" רשום רק תרופות חדשות שהרופא רשם במהלך הביקור הנוכחי.
- אל תכלול תרופות כרוניות שהמטופל כבר לוקח (הן רשומות בקטגוריית "תרופות כרוניות").
- אם לא נרשמו תרופות חדשות, כתוב "אין מרשמים".

## מבנה הסיכום:

השתמש במבנה הבא בדיוק. אל תוסיף סעיפים ואל תשמיט סעיפים:

---רקע דמוגרפי---

• גיל: [גיל או "לא צוין"]
• מין: [זכר/נקבה או "לא צוין"]
• מצב משפחתי: [מצב או "לא צוין"]
• מגורים: [מגורים או "לא צוין"]
• עיסוק: [עיסוק או "לא צוין"]

---רקע רפואי---

• מחלות ברקע: [רשימת מחלות מהתמלול או "לא צוין"]
• תרופות כרוניות:
[רשימת תרופות — כל תרופה בשורה חדשה, עם מינון אם צוין]
• אלרגיות: [אלרגיות מהתמלול או "לא צוין"]

---תלונה עיקרית---

• [התלונה שבגללה הגיע המטופל]

---פרטי המחלה הנוכחית---

• [תיאור מפורט של המחלה/בעיה הנוכחית כפי שעולה מהתמלול]

---בדיקה גופנית---

[ממצאים שתוארו בתמלול או "לא צוין"]

---תוצאות מעבדה---

[תוצאות שהוזכרו בתמלול או "לא צוין"]

---דימות ובדיקות עזר---

[בדיקות דימות שהוזכרו בתמלול או "לא בוצע"]

---סיכום רפואי של הרופא---

• מסקנה: [סיכום מתומצת של המקרה על בסיס התמלול בלבד]

---המלצות---

[רשימת המלצות שהרופא נתן בתמלול]

---מרשמים---

[תרופות חדשות שנרשמו בביקור זה, או "אין מרשמים"]
אם נרשם מרשם, רשום כך:
1. שם התרופה: [שם]
   מינון: [מינון או "לא צוין"]
   משך טיפול: [משך או "לא צוין"]
"""


VALIDATION_PROMPT = """אתה מערכת בקרת איכות לסיכום רפואי. 
קיבלת שני דברים:
1. תמלול מקורי של שיחה רופא-מטופל
2. סיכום רפואי שנוצר מהתמלול

בדוק את הסיכום לפי הקריטריונים הבאים ודווח ב-JSON בלבד:

{
  "hallucinated_medications": ["רשימת תרופות שמופיעות בסיכום אבל לא בתמלול"],
  "duplicate_medications": ["רשימת זוגות תרופות שהן בעצם אותה תרופה בשמות שונים"],
  "suspicious_dosages": ["תיאור מינונים חשודים"],
  "fabricated_info": ["מידע שמופיע בסיכום אבל לא בתמלול"],
  "chief_complaint_ok": true/false,
  "chief_complaint_note": "הערה אם התלונה העיקרית לא נכונה",
  "overall_faithfulness_score": 0-10
}

היה קפדני מאוד. כל פיסת מידע בסיכום חייבת להתבסס על התמלול.
"""


# ─────────────────────────────────────────────────────────────────────────────
# Dataclass for summary report
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class MedicalSummaryReport:
    """Audit trail for the medical summary step."""
    summary_text: str = ""
    # Validation results
    hallucinated_medications: List[str] = field(default_factory=list)
    duplicate_medications: List[Tuple[str, str]] = field(default_factory=list)
    suspicious_dosages: List[str] = field(default_factory=list)
    fabricated_info: List[str] = field(default_factory=list)
    chief_complaint_ok: bool = True
    chief_complaint_note: str = ""
    faithfulness_score: float = 0.0
    # Deterministic checks
    meds_in_transcript: List[str] = field(default_factory=list)
    meds_in_summary: List[str] = field(default_factory=list)
    deterministic_duplicate_pairs: List[Tuple[str, str]] = field(default_factory=list)
    deterministic_dosage_warnings: List[str] = field(default_factory=list)
    validation_passed: bool = True

    def to_dict(self) -> dict:
        return {
            "hallucinated_medications": self.hallucinated_medications,
            "duplicate_medications": [list(pair) for pair in self.duplicate_medications],
            "suspicious_dosages": self.suspicious_dosages,
            "fabricated_info": self.fabricated_info,
            "chief_complaint_ok": self.chief_complaint_ok,
            "chief_complaint_note": self.chief_complaint_note,
            "faithfulness_score": self.faithfulness_score,
            "meds_in_transcript": self.meds_in_transcript,
            "meds_in_summary": self.meds_in_summary,
            "deterministic_duplicate_pairs": [list(p) for p in self.deterministic_duplicate_pairs],
            "deterministic_dosage_warnings": self.deterministic_dosage_warnings,
            "validation_passed": self.validation_passed,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Medical Summary Generator
# ─────────────────────────────────────────────────────────────────────────────

class MedicalSummaryGenerator:
    """Generates and validates a structured medical summary from a transcription."""

    def __init__(self, gpt52_client):
        self.client = gpt52_client
        self.report = MedicalSummaryReport()

    # ── Main entry point ──────────────────────────────────────────────────

    def generate(
        self,
        transcription: str,
        trace: Optional["PipelineTrace"] = None,
    ) -> Tuple[str, MedicalSummaryReport]:
        """
        Generate a medical summary from the transcription.

        Returns:
            (summary_text, report)
        """
        # Step 1: Generate summary via LLM
        if trace:
            trace.start_timer("step_6a_summary_draft")

        raw_summary = self._call_llm_generate(transcription)

        if trace:
            trace.add_step(
                "step_6a_summary_draft", raw_summary,
                metadata={"model": "gpt-5.2-chat", "task": "medical_summary_generation"}
            )

        # Step 2: Deterministic validation (no LLM)
        if trace:
            trace.start_timer("step_6b_summary_validation")

        self._deterministic_validation(transcription, raw_summary)

        # Step 3: LLM-based validation (cross-check)
        llm_validation = self._call_llm_validate(transcription, raw_summary)
        self._apply_llm_validation(llm_validation)

        # Step 4: Apply fixes — inject warnings into summary text
        final_summary = self._inject_warnings(raw_summary)

        self.report.summary_text = final_summary
        self.report.validation_passed = (
            len(self.report.hallucinated_medications) == 0
            and len(self.report.fabricated_info) == 0
            and self.report.chief_complaint_ok
            and self.report.faithfulness_score >= 7
        )

        if trace:
            trace.add_step(
                "step_6b_summary_validation", final_summary,
                metadata={
                    "task": "summary_validation",
                    "validation_passed": self.report.validation_passed,
                    "faithfulness_score": self.report.faithfulness_score,
                    "issues_found": (
                        len(self.report.hallucinated_medications)
                        + len(self.report.duplicate_medications)
                        + len(self.report.suspicious_dosages)
                        + len(self.report.fabricated_info)
                    ),
                }
            )

        return final_summary, self.report

    # ── LLM calls ─────────────────────────────────────────────────────────

    def _call_llm_generate(self, transcription: str) -> str:
        """Ask GPT-5.2 to produce the structured medical summary."""
        response = self.client.chat.completions.create(
            model="gpt-5.2-chat",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "הנה תמלול השיחה הרפואית. צור סיכום רפואי מובנה על בסיס התמלול בלבד.\n\n"
                        f"{transcription}"
                    ),
                },
            ],
        )
        return response.choices[0].message.content.strip()

    def _call_llm_validate(self, transcription: str, summary: str) -> dict:
        """Ask GPT-5.2 to cross-check the summary against the transcript."""
        try:
            response = self.client.chat.completions.create(
                model="gpt-5.2-chat",
                messages=[
                    {"role": "system", "content": VALIDATION_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            "## תמלול מקורי:\n\n"
                            f"{transcription}\n\n"
                            "## סיכום רפואי:\n\n"
                            f"{summary}"
                        ),
                    },
                ],
            )
            raw = response.choices[0].message.content.strip()
            # Extract JSON from response (handle markdown code blocks)
            json_match = re.search(r'\{[\s\S]*\}', raw)
            if json_match:
                return json.loads(json_match.group())
            return {}
        except Exception as e:
            print(f"   ⚠️  LLM validation failed: {e}")
            return {}

    # ── Deterministic validation ──────────────────────────────────────────

    def _deterministic_validation(self, transcription: str, summary: str):
        """Run rule-based checks that don't need an LLM."""
        self._check_medication_duplicates(summary)
        self._check_dosage_plausibility(summary)
        self._extract_medication_lists(transcription, summary)

    def _extract_medication_lists(self, transcription: str, summary: str):
        """Extract medication names from both texts for cross-reference."""
        # Collect all known medication names that appear in each text
        transcript_lower = transcription.lower()
        summary_lower = summary.lower()

        all_med_names = set()
        for group in MEDICATION_EQUIVALENCES:
            all_med_names.update(group)

        self.report.meds_in_transcript = sorted(
            [m for m in all_med_names if m.lower() in transcript_lower]
        )
        self.report.meds_in_summary = sorted(
            [m for m in all_med_names if m.lower() in summary_lower]
        )

    def _check_medication_duplicates(self, summary: str):
        """Detect brand/generic name duplicates in the summary."""
        summary_lower = summary.lower()
        found_groups: Dict[int, List[str]] = {}

        for group_idx, group in enumerate(MEDICATION_EQUIVALENCES):
            found_names = []
            for name in group:
                # Check various forms
                if name.lower() in summary_lower:
                    found_names.append(name)
            if len(found_names) > 1:
                found_groups[group_idx] = found_names

        for group_idx, names in found_groups.items():
            for i in range(len(names)):
                for j in range(i + 1, len(names)):
                    pair = (names[i], names[j])
                    self.report.deterministic_duplicate_pairs.append(pair)

    def _check_dosage_plausibility(self, summary: str):
        """Check if dosages mentioned in the summary are within normal ranges."""
        # Pattern: medication name followed by a number and "mg"
        dosage_pattern = re.compile(
            r'(\w+[\w\-]*)\s+(\d+(?:\.\d+)?)\s*(?:mg|מ"ג|מג)',
            re.IGNORECASE
        )
        for match in dosage_pattern.finditer(summary):
            drug_name = match.group(1).lower()
            dosage = float(match.group(2))

            if drug_name in DOSAGE_RANGES:
                min_dose, max_dose = DOSAGE_RANGES[drug_name]
                if dosage < min_dose * 0.5 or dosage > max_dose * 1.5:
                    warning = (
                        f"{match.group(1)} {match.group(2)} mg — "
                        f"מינון חריג (טווח סטנדרטי: {min_dose}-{max_dose} mg). "
                        f"ייתכן שגיאת תמלול."
                    )
                    self.report.deterministic_dosage_warnings.append(warning)

    # ── Apply LLM validation to report ────────────────────────────────────

    def _apply_llm_validation(self, validation: dict):
        """Merge LLM validation results into the report."""
        if not validation:
            return

        self.report.hallucinated_medications = validation.get(
            "hallucinated_medications", []
        )
        self.report.duplicate_medications = [
            tuple(pair) if isinstance(pair, list) else (pair, "")
            for pair in validation.get("duplicate_medications", [])
        ]
        self.report.suspicious_dosages = validation.get("suspicious_dosages", [])
        self.report.fabricated_info = validation.get("fabricated_info", [])
        self.report.chief_complaint_ok = validation.get("chief_complaint_ok", True)
        self.report.chief_complaint_note = validation.get("chief_complaint_note", "")
        self.report.faithfulness_score = validation.get(
            "overall_faithfulness_score", 0
        )

    # ── Inject warnings into the summary ──────────────────────────────────

    def _inject_warnings(self, summary: str) -> str:
        """Add warning annotations to the summary where issues were found."""
        lines = summary.split("\n")
        warnings_section = []

        # Collect all warnings
        if self.report.hallucinated_medications:
            for med in self.report.hallucinated_medications:
                warnings_section.append(
                    f"⚠️ תרופה שייתכן שלא הוזכרה בתמלול: {med}"
                )

        if self.report.deterministic_duplicate_pairs:
            for name1, name2 in self.report.deterministic_duplicate_pairs:
                warnings_section.append(
                    f"⚠️ כפילות תרופתית אפשרית: {name1} ו-{name2} הן ככל הנראה אותה תרופה"
                )

        if self.report.deterministic_dosage_warnings:
            for warning in self.report.deterministic_dosage_warnings:
                warnings_section.append(f"⚠️ {warning}")

        if self.report.suspicious_dosages:
            for dosage_issue in self.report.suspicious_dosages:
                if dosage_issue not in str(self.report.deterministic_dosage_warnings):
                    warnings_section.append(f"⚠️ מינון חשוד: {dosage_issue}")

        if self.report.fabricated_info:
            for info in self.report.fabricated_info:
                warnings_section.append(
                    f"⚠️ מידע שייתכן שלא הוזכר בתמלול: {info}"
                )

        if not self.report.chief_complaint_ok:
            warnings_section.append(
                f"⚠️ תלונה עיקרית: {self.report.chief_complaint_note}"
            )

        # If there are warnings, add a warnings section at the end
        if warnings_section:
            lines.append("")
            lines.append("")
            lines.append("---אזהרות בקרת איכות---")
            lines.append("")
            for w in warnings_section:
                lines.append(f"• {w}")

        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Helper for report formatting
# ─────────────────────────────────────────────────────────────────────────────

def format_summary_report(report: MedicalSummaryReport) -> str:
    """Format the summary report for console output."""
    parts = ["📋 MEDICAL SUMMARY REPORT"]
    parts.append(f"   Faithfulness score: {report.faithfulness_score}/10")
    parts.append(f"   Validation passed: {'✅' if report.validation_passed else '❌'}")

    if report.hallucinated_medications:
        parts.append(f"   ⚠️  Hallucinated meds: {', '.join(report.hallucinated_medications)}")
    if report.deterministic_duplicate_pairs:
        pairs = [f"{a}={b}" for a, b in report.deterministic_duplicate_pairs]
        parts.append(f"   ⚠️  Duplicate meds: {', '.join(pairs)}")
    if report.deterministic_dosage_warnings:
        parts.append(f"   ⚠️  Dosage warnings: {len(report.deterministic_dosage_warnings)}")
        for w in report.deterministic_dosage_warnings:
            parts.append(f"      - {w}")
    if report.fabricated_info:
        parts.append(f"   ⚠️  Fabricated info: {', '.join(report.fabricated_info)}")
    if not report.chief_complaint_ok:
        parts.append(f"   ⚠️  Chief complaint issue: {report.chief_complaint_note}")

    return "\n".join(parts)
