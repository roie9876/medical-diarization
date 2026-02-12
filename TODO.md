# TODO — Spelling Correction Improvement (Top Priority)

> **Status**: Investigation phase  
> **Problem**: Stage B uses a hard-coded dictionary of ~30 words found in specific sample conversations. This does not generalize to new conversations with unknown vocabulary. A production system must handle any Hebrew medical conversation without prior knowledge of the words in it.

---

## Core Problem

GPT-Audio produces **predictable categories of Hebrew errors**, but the **specific wrong words are unpredictable** — they depend on the speaker's accent, speech speed, background noise, and medical jargon used. A static lookup table cannot scale.

### Error patterns observed so far

| Pattern | Example | Root cause |
|---------|---------|------------|
| ה ↔ ע confusion | עזות → הזעות | Phonetically identical in most Hebrew dialects |
| כ ↔ ק confusion | בכום → בקרום | Similar pharyngeal sounds |
| Dropped/added letters | בליסה → בלעיסה | Fast speech, model uncertainty |
| Phonetic anagrams | חטפם → התקף | Similar sound, different segmentation |
| Drug name garbling | קרדיולוק → קרדילול | Model unfamiliar with drug names |
| Hebrew→English normalization | אולטרסאונד → Ultrasound | Transliteration vs. standard form |

---

## Investigation Items

### 1. Hebrew Phonetic Similarity Model

**Idea**: Build a phonetic distance function for Hebrew that can detect when a transcribed word is phonetically close to a known correct word.

- [ ] Research Hebrew phonetic encoding (equivalent of Soundex/Metaphone for Hebrew)
- [ ] Map Hebrew letter confusion pairs: ה↔ע, כ↔ק, ח↔ה, ט↔ת, ב↔ו, שׂ↔שׁ, etc.
- [ ] Prototype a function that scores phonetic similarity between two Hebrew words
- [ ] Test: given a wrong word, can it find the right word from a medical dictionary?

**Pros**: Addresses the root cause (phonetic confusion), generalizes to unknown words  
**Cons**: Needs a reference dictionary of correct Hebrew words to compare against

### 2. Hebrew Medical Terminology Database

**Idea**: Instead of listing wrong words, maintain a database of **correct** medical Hebrew words. Any transcribed word that is "close but not in the dictionary" gets flagged and auto-corrected to the nearest match.

- [ ] Research existing Hebrew medical term databases (SNOMED-CT Hebrew, Ministry of Health terminology)
- [ ] Research Hebrew morphological analyzers (HSpell, MILA, Dicta) that can validate word correctness
- [ ] Evaluate [Dicta](https://dicta.org.il/) — Israeli NLP tools for Hebrew spell checking
- [ ] Build a medical Hebrew lexicon: body parts, conditions, medications, procedures
- [ ] Combine with phonetic similarity (item 1) for correction candidates

**Pros**: Scales to any conversation, catches errors we haven't seen before  
**Cons**: Needs comprehensive dictionary, Hebrew morphology is complex (prefixes, suffixes, conjugations)

### 3. Hebrew Spell-Check as a Service

**Idea**: Use existing Hebrew NLP spell-checkers to flag and correct errors before/instead of our custom dictionary.

- [ ] Evaluate [HSpell](http://hspell.ivrix.org.il/) — open-source Hebrew spell checker
- [ ] Evaluate [Dicta Spell Checker](https://dicta.org.il/spell-checker) — neural Hebrew spelling
- [ ] Evaluate [AlephBERT](https://huggingface.co/onlplab/alephbert-base) — Hebrew BERT for contextual correction
- [ ] Test each on our known error set — how many do they catch?
- [ ] Measure false positive rate — do they "correct" words that are actually right?

**Pros**: Leverages existing Hebrew NLP research, handles morphology  
**Cons**: May not know medical terms, may need domain-specific fine-tuning

### 4. Medication & Drug Name Handling

**Idea**: Drug names are a special category — they're not Hebrew words, so Hebrew spell-checkers won't help. Need a separate strategy.

- [ ] Build a database of common Israeli medication names (Hebrew transliterations + English originals)
- [ ] Use fuzzy matching (Levenshtein / phonetic) against this drug database
- [ ] Research the Israeli Pharmaceutical Guide (פנקס התרופות) as a data source
- [ ] Consider always outputting drug names in English (current behavior) — but need to recognize the Hebrew form first

### 5. Contextual LLM Correction (Improved Stage D)

**Idea**: Instead of a dictionary, use an LLM more effectively — but with a structured approach rather than free-form "fix everything."

- [ ] Two-pass approach: first ask LLM to **identify** suspicious words, then ask to **suggest corrections**
- [ ] Provide the LLM with a medical context window (what is this conversation about?) for better corrections
- [ ] Use few-shot examples of common error patterns to guide the LLM
- [ ] Research: can we ask GPT to output a confidence score per word during transcription?
- [ ] Evaluate cost/latency trade-off of more LLM calls vs. quality improvement

### 6. Feedback Loop / Self-Learning Dictionary

**Idea**: When a human reviews and corrects a transcription, automatically learn new dictionary entries.

- [ ] Design a correction feedback format (original → corrected pairs)
- [ ] Build a tool that diffs manual corrections against raw output and extracts new dictionary entries
- [ ] Accumulate corrections across conversations into a growing dictionary
- [ ] Periodically review and merge into the static dictionary (human-in-the-loop)
- [ ] Track correction frequency — if the same error appears N times, auto-promote to dictionary

**Pros**: Gets better over time, leverages real usage data  
**Cons**: Requires human review infrastructure, cold-start problem

### 7. Multi-Transcription Consensus

**Idea**: We already run two parallel transcriptions (Steps 1 & 2). If a word differs between them, flag it as uncertain and apply extra scrutiny.

- [ ] Compare pure transcription vs. diarized transcription word-by-word
- [ ] Words that agree → high confidence, keep as-is
- [ ] Words that differ → uncertain, run through phonetic/spell-check pipeline
- [ ] Could run 3+ transcription passes for majority voting (cost trade-off)

**Pros**: No external dependencies, uses signals already available  
**Cons**: Both passes may make the same error, adds comparison complexity

---

## Recommended Investigation Order

| Priority | Item | Effort | Expected Impact |
|----------|------|--------|----------------|
| 🔴 1 | Hebrew Spell-Check as a Service (#3) | Low | High — quick win, existing tools |
| 🔴 2 | Medication Name Database (#4) | Medium | High — drug names are critical |
| 🟡 3 | Feedback Loop (#6) | Medium | High — improves over time |
| 🟡 4 | Multi-Transcription Consensus (#7) | Low | Medium — leverages existing data |
| 🟡 5 | Phonetic Similarity Model (#1) | High | High — addresses root cause |
| 🔵 6 | Medical Terminology Database (#2) | High | High — long-term solution |
| 🔵 7 | Improved LLM Correction (#5) | Medium | Medium — better use of existing infra |

---

## What to Keep from Current Approach

The static dictionary is not useless — it should become **one layer** in a multi-layered correction system:

1. **Layer 1**: Static dictionary (current) — fast, zero-cost, 100% precision for known errors
2. **Layer 2**: Hebrew spell-checker — catches general Hebrew errors
3. **Layer 3**: Medical term / drug name fuzzy matcher — catches domain-specific errors
4. **Layer 4**: Phonetic similarity — catches sound-alike errors
5. **Layer 5**: LLM-based contextual fix (current Stage D) — catches everything else

Each layer passes its output to the next. The static dictionary stays as a fast first pass, but it's no longer the **only** defense.
