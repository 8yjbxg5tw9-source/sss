# English Vocabulary Master — A1 to C2 (English → Azerbaijani)

A network-based English vocabulary curriculum for Azerbaijani-speaking learners, stored as plain TXT
files and generated from hand-written lesson sources by one Python script.

Every **main word** is taught as the hub of a small network:

* spelling, Azerbaijani meaning, part of speech, British IPA, CEFR level;
* its word family (noun / verb / adjective / adverb forms);
* 7–8 natural expressions and collocations, each with an Azerbaijani translation and a usage note;
* 4 example sentences with translation;
* a usage explanation (in Azerbaijani for A1–A2, in English for B1–C2).

One rule governs the whole system: **every word is taught only once between A1 and C2.** A global
checker refuses to build if a word is taught a second time (see "The no-repetition rule" below).

## Where the lessons are

Open the files in `ENGLISH_VOCABULARY_MASTER/` — these are the deliverables:

| File | Contents |
| --- | --- |
| `MASTER_INDEX.txt` | rules, statistics, the six tracking records (main words, all items, all expressions, word families, CEFR classification, duplicate status), roadmap, how to continue |
| `A1_VOCABULARY.txt` … `C2_VOCABULARY.txt` | the lessons of each level, unit by unit, with an updated index after every unit |
| `GLOBAL_LEARNED_WORDS.txt` | every vocabulary item A–Z with its level, lesson and the expression that teaches it |

Machine-readable copies live in `database/` (`vocabulary_db.json`, `learned_words.tsv`), together with
`qa_report.txt`, the automatic quality report.

All of these files are **generated**. Never edit them by hand: edit `source/` and rebuild.

### Size of the current edition

| Level | Units | Main words | Family forms | New words in expressions | Expressions | Sentences |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A1 | 7 | 40 | 40 | 317 | 320 | 160 |
| A2 | 7 | 40 | 55 | 264 | 320 | 160 |
| B1 | 5 | 41 | 79 | 264 | 328 | 164 |
| B2 | 4 | 40 | 75 | 298 | 320 | 160 |
| C1 | 6 | 60 | 100 | 444 | 480 | 240 |
| C2 | 6 | 60 | 66 | 451 | 480 | 240 |
| **Total** | **35** | **281** | **415** | **2,038** | **2,248** | **1,124** |

2,753 vocabulary items in total (the rows above plus 19 reference words: days and months), and 245
structural grammar words that are taught once in A1 "Section 0". C1 and C2 carry extra weight on
purpose: they hold the academic and IELTS vocabulary. The authoritative, always current figures are
in section 3 of `MASTER_INDEX.txt`; section 11 lists 78 further main words that are already reserved
for the next parts.

## What this is not

* It is **not every English word**. It is a finite, growing database. Measured against the open
  reference lists it currently covers about 69% of A1 headwords, 45% of A2, 31% of B1, 17% of B2,
  12% of C1 and 8% of C2 (`database/qa_report.txt`, section COVERAGE).
* **CEFR levels are not universally fixed.** Each lesson was placed at a level by the author according
  to the difficulty of the expression network it teaches, and then compared with two open word lists.
  Those lists rate many bare headwords lower than the lesson (for example TRAVEL: A1 in the list, A2
  here). Every such lesson carries a "Level note", and the QA report lists all of them.
* The Azerbaijani translations, the IPA and the usage notes were **written by an AI system**. The IPA
  of every main word was compared automatically with open pronunciation lists (see "Quality checks"),
  but no native-speaker editor has proof-read the translations. Treat the text as a carefully built
  draft and report anything that looks wrong.

## The no-repetition rule (as enforced by the checker)

1. One database for all levels; it is never reset.
2. Inside an expression every word must be
   (a) the lesson's main word or one of its listed family forms, **or**
   (b) a structural word (articles, pronouns, prepositions, auxiliaries … listed in
   `source/00_foundation.txt`), **or**
   (c) a brand-new word, which the expression then teaches.
   A word taught in any other lesson is rejected (`DUPLICATE`), and so is a word that the roadmap
   reserves as a future main word (`RESERVED`).
3. Matching uses dictionary forms, conservatively: plural, -ed, -ing and irregular forms count as
   the same word (meet / meeting, hide / hidden / hiding, child / children).
4. Look-alikes that really are different words (new / news, glass / glasses, wind / wound) must be
   declared one by one, with a reason, in `source/distinct_lexemes.txt`. They are printed in Record 6
   of the master index.
5. Every expression is unique. Example sentences and usage notes may freely reuse known words; that
   is where frequent collocations of two already-taught words are shown (for example "climate
   change", "take into account").

A consequence worth knowing: because a word can be spent only once, some very common collocations
cannot be *taught* as expressions (they appear in examples and notes instead), and derived words that
are not listed in a lesson's family (heavy → heavily) count as new words.

## Repository layout

```
tools/vocab.py                 builder + global duplicate checker (Python 3, standard library only)
source/00_foundation.txt       structural words and reference sets (A1 "Section 0")
source/<LEVEL>/NN_name.txt     hand-written lessons, one file per unit, read in file-name order
source/roadmap.txt             main words reserved for lessons that are not written yet
source/distinct_lexemes.txt    look-alike pairs declared to be different words (with reasons)
source/lemma_overrides.txt     dictionary form to register for a token when the automatic rule is wrong
source/related.txt             confirmed word-family links between different lessons (shown to learners)
source/not_related.txt         rejected look-alike links (bus / busy, read / ready …)
source/ipa_reviewed.txt        IPA that differs from the fallback list and was kept after review
source/reference_levels.tsv    reference-list level of every main word (written by the build, see Credits)
ENGLISH_VOCABULARY_MASTER/     generated TXT deliverables
database/                      generated JSON / TSV database and QA report
```

## Lesson source format

Blank lines and lines starting with `//` are ignored.

```
## Unit title in English | Unit title in Azerbaijani
@ WORD | part of speech | ipa without slashes | Azerbaijani meaning
forms: go – goes – went – gone – going            (optional key forms)
n: noun = az; noun = az                            (family forms; also v: adj: adv:)
- expression with the main word = az :: usage note
~ related expression without the main word = az :: usage note
> English example sentence. = Azerbaijani translation.
! Usage explanation paragraph.
```

Rules checked on every lesson: exactly four fields after `@`; 7–8 expressions, each with a `::`
note; 3–5 example sentences; at least one `!` paragraph; IPA limited to the standard symbol set
(use `ɡ` U+0261, not ASCII `g`); a `-` expression must contain the main word or a family form; a `~`
expression must introduce at least one new word. **Do not put `;` inside a family-form gloss** – it
separates forms (write `, həmçinin` instead).

## Commands

```
python3 tools/vocab.py build              # validate everything and regenerate all output files
python3 tools/vocab.py check PLAN_FILE    # test planned lessons against the database before writing them
python3 tools/vocab.py find WORD ...      # where is a word taught? (or STRUCTURAL / not in database)
python3 tools/vocab.py free WORD ...      # which of these words are still unused?
```

If the build finds a single error it writes nothing, so the published files are always consistent.

A plan file has one lesson per line:

```
B2 ANALYSE + analysis, analyst, analytical :: statistical analysis | a thorough analysis | ~ related expression | ...
```

## How to add lessons (also for a later session)

1. Choose main words (see `source/roadmap.txt`; add new ones there to reserve them).
2. Write a plan line for each lesson and run `check` until it reports `0 problems`. Typical
   problems: a collocate was already taught (pick another collocation), or two lessons of the same
   plan want the same word.
3. Write the lessons into `source/<LEVEL>/NN_name.txt` in the format above, keeping the style of the
   existing units (British spelling and IPA, Azerbaijani settings in examples).
4. Run `build`. Fix every error and warning.
5. Read `database/qa_report.txt`: level comparison, above-level collocates, IPA comparison, and the
   list of unreviewed word-family link candidates (move each pair to `related.txt` or
   `not_related.txt`).
6. Remove the finished words from `source/roadmap.txt` and commit.

Level files split automatically into `<LEVEL>_VOCABULARY_PART_02.txt` … when a level grows beyond
80 lessons, and the global word list splits at 9,000 lines.

## Quality checks

`build` runs these checks and writes the results to `database/qa_report.txt`:

* **Duplicates** – blocking; the build fails.
* **Level comparison** – each main word against the CEFR-J list (A1–B2) and the Octanove list
  (C1–C2); collocates rated two or more levels above their lesson are listed.
* **IPA comparison** – each main word against Britfone, and against a second open list (ipa-dict
  `en_UK`) for words Britfone lacks. Differences that are only weak-vowel notation (i/ɪ, ɪ/ə, tj/tʃ)
  are counted as variants. Fourteen rarer C1/C2 words differ from the second list; they were re-checked
  by the author and kept, with the reason for each in `source/ipa_reviewed.txt`. That re-check is an
  author's judgement made without online dictionary access, not a machine verification.
* **Word-family links** – only pairs confirmed in `source/related.txt` are shown to learners.

The reference data is optional and is **not** part of this repository. To enable the comparison,
clone it next to the repository (or point `VOCAB_REFDATA` at the folder):

```
mkdir ../refdata && cd ../refdata
git clone --depth 1 https://github.com/openlanguageprofiles/olp-en-cefrj.git
git clone --depth 1 https://github.com/JoseLlarena/Britfone.git
git clone --depth 1 --filter=blob:none --sparse https://github.com/open-dict-data/ipa-dict.git
(cd ipa-dict && git sparse-checkout set --no-cone data/en_UK.txt)
```

Without it the build still works and the lesson files come out identical, because the levels are
cached in `source/reference_levels.tsv`. Only the comparison itself is skipped: the cross-check
summary disappears from `MASTER_INDEX.txt` and `database/qa_report.txt` is not refreshed.

## Credits for reference data

* The CEFR-J Wordlist Version 1.5. Compiled by Yukio Tono, Tokyo University of Foreign Studies.
  Retrieved from http://www.cefr-j.org/download.html (via the Open Language Profiles repository).
* Octanove Vocabulary Profile C1/C2 (ver 1.0), Octanove Labs, licensed CC BY-SA 4.0.
* Britfone 3.0.1 by Jose Llarena (MIT licence) and ipa-dict (open-dict-data) were used locally for
  the pronunciation comparison only.

`source/reference_levels.tsv` and the "Level note" lines quote the level these lists give to the
main words of this course; the C1/C2 entries derive from the Octanove list and are therefore shared
under CC BY-SA 4.0. No other reference data is redistributed here.
