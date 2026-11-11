#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vocab.py - builder and global duplicate checker for the
ENGLISH VOCABULARY MASTER SYSTEM (A1 to C2, English -> Azerbaijani).

Standard library only.  Usage (run from anywhere):

  python3 tools/vocab.py build          validate every lesson, then regenerate all TXT files
  python3 tools/vocab.py check FILE|-   dry-run a plan of NEW lessons against the database
  python3 tools/vocab.py find WORD...   look words up in the database
  python3 tools/vocab.py free WORD...   say which of the given words are still unused

Source of truth:  source/   (hand-written lesson files, see README.md)
Generated output: ENGLISH_VOCABULARY_MASTER/*.txt  and  database/*.json|tsv
"""
import sys, os, re, json, textwrap, datetime
from collections import defaultdict, OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'source')
OUT = os.path.join(ROOT, 'ENGLISH_VOCABULARY_MASTER')
DBD = os.path.join(ROOT, 'database')
REF = os.environ.get('VOCAB_REFDATA', os.path.join(os.path.dirname(ROOT), 'refdata'))

LEVELS = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']
LEVEL_NAME = {'A1': 'Beginner', 'A2': 'Elementary', 'B1': 'Intermediate',
              'B2': 'Upper Intermediate', 'C1': 'Advanced', 'C2': 'Proficiency'}
LEVEL_AZ = {'A1': 'Başlanğıc səviyyə', 'A2': 'Elementar səviyyə', 'B1': 'Orta səviyyə',
            'B2': 'Ortadan yuxarı səviyyə', 'C1': 'Yüksək səviyyə', 'C2': 'Mükəmməl səviyyə'}
WIDTH = 100
MAX_LESSONS_PER_FILE = 80      # a level file is split into numbered parts above this size
MAX_ITEMS_PER_GLOBAL_FILE = 9000
CATS = [('n', 'Noun forms'), ('v', 'Verb forms'), ('adj', 'Adjective forms'), ('adv', 'Adverb forms')]

TOKEN_RE = re.compile(r"[^\W\d_]+(?:['-][^\W\d_]+)*")

# ------------------------------------------------------------------ morphology
_IRREG_VERBS = """be was were been|bear bore borne born|beat beaten|become became|begin began begun|bend bent
|bet|bind bound|bite bit bitten|bleed bled|blow blew blown|break broke broken|breed bred|bring brought
|build built|burn burnt|buy bought|catch caught|choose chose chosen|cling clung|come came|creep crept
|deal dealt|dig dug|do did done|draw drew drawn|dream dreamt|drink drank drunk|drive drove driven
|eat ate eaten|fall fell fallen|feed fed|feel felt|fight fought|find found|flee fled|fly flew flown
|forbid forbade forbidden|forget forgot forgotten|forgive forgave forgiven|freeze froze frozen|get got gotten
|give gave given|go went gone|grow grew grown|hang hung|have had|hear heard|hide hid hidden|hold held
|keep kept|know knew known|lay laid|lead led|learn learnt|leave left|lend lent|lie lay lain|light lit
|lose lost|make made|mean meant|meet met|pay paid|ride rode ridden|ring rang rung|rise rose risen|run ran
|say said|see saw seen|seek sought|sell sold|send sent|shake shook shaken|shine shone|shoot shot
|show shown|shrink shrank shrunk|sing sang sung|sink sank sunk|sit sat|sleep slept|slide slid
|speak spoke spoken|spend spent|spin spun|spring sprang sprung|stand stood|steal stole stolen|stick stuck
|sting stung|strike struck|swear swore sworn|sweep swept|swim swam swum|swing swung|take took taken
|teach taught|tear tore torn|tell told|think thought|throw threw thrown|understand understood
|wake woke woken|wear wore worn|weep wept|win won|wind wound|withdraw withdrew withdrawn
|write wrote written|undergo underwent undergone|overcome overcame|undertake undertook undertaken
|arise arose arisen|foresee foresaw foreseen|mislead misled|overtake overtook overtaken|uphold upheld
|withhold withheld|withstand withstood|strive strove striven|tread trod trodden|weave wove woven
|sow sown|sew sewn|lean leant|leap leapt|spell spelt|spill spilt|spoil spoilt|smell smelt|kneel knelt
|dwell dwelt|grind ground|man men|woman women|child children|foot feet|tooth teeth|mouse mice|goose geese
|life lives|knife knives|wife wives|leaf leaves|shelf shelves|half halves|wolf wolves|thief thieves
|loaf loaves|self selves|criterion criteria|phenomenon phenomena|analysis analyses|crisis crises
|thesis theses|hypothesis hypotheses|basis bases|diagnosis diagnoses|index indices|stimulus stimuli
|curriculum curricula|good better best|bad worse worst|far further furthest farther"""
IRREG_BACK = defaultdict(set)   # inflected form -> base(s)
IRREG_FWD = defaultdict(set)    # base -> inflected forms
for _grp in _IRREG_VERBS.replace('\n', '').split('|'):
    _w = _grp.split()
    for _f in _w[1:]:
        IRREG_BACK[_f].add(_w[0])
        IRREG_FWD[_w[0]].add(_f)
# comparatives are separate teaching items, so they are not treated as collisions with good/bad/far
for _b in ('good', 'bad', 'far'):
    for _f in list(IRREG_FWD[_b]):
        IRREG_BACK[_f].discard(_b)

NO_SING = set("""news series species means clothes jeans trousers scissors glasses goods thanks savings
earnings surroundings premises customs headquarters outskirts remains contents odds always perhaps sometimes
towards besides lens gas bus plus yes this his its was has does is as us thus across less unless chaos cosmos
ethos bias atlas canvas christmas pyjamas measles diabetes athletics gymnastics aerobics mathematics maths
physics economics politics ethics statistics linguistics electronics genetics mechanics logistics analysis
crisis basis thesis emphasis hypothesis diagnosis synthesis oasis tennis chess sunglasses shorts tights
stairs upstairs downstairs indoors outdoors overseas nowadays afterwards backwards forwards ms mrs lots
whereabouts proceeds belongings congratulations regards""".split())
_OES = {'potatoes', 'tomatoes', 'heroes', 'echoes', 'mosquitoes', 'volcanoes', 'vetoes'}
_SES = {'buses': 'bus', 'viruses': 'virus', 'bonuses': 'bonus', 'focuses': 'focus', 'campuses': 'campus',
        'gases': 'gas', 'statuses': 'status', 'surpluses': 'surplus', 'censuses': 'census',
        'lenses': 'lens', 'crises': 'crisis', 'analyses': 'analysis', 'theses': 'thesis'}
_VES = {'lives': 'life', 'knives': 'knife', 'wives': 'wife', 'leaves': 'leaf', 'shelves': 'shelf',
        'halves': 'half', 'wolves': 'wolf', 'thieves': 'thief', 'loaves': 'loaf', 'selves': 'self',
        'scarves': 'scarf', 'calves': 'calf'}
_IRR_PL = {'men': 'man', 'women': 'woman', 'children': 'child', 'feet': 'foot', 'teeth': 'tooth',
           'mice': 'mouse', 'geese': 'goose', 'criteria': 'criterion', 'phenomena': 'phenomenon',
           'hypotheses': 'hypothesis', 'diagnoses': 'diagnosis', 'stimuli': 'stimulus'}


def lemma_of(tok):
    """Dictionary form used to DISPLAY a newly introduced collocate (plural nouns -> singular)."""
    low = tok.lower()
    if '-' in low or "'" in low:
        return tok
    if low in _IRR_PL:
        r = _IRR_PL[low]
        return r.capitalize() if tok[0].isupper() else r
    if low in NO_SING or len(low) <= 3 or not low.endswith('s'):
        return tok
    if low.endswith(('ss', 'us', 'is', 'ics', 'ous')):
        return tok
    if low in _VES:
        return _VES[low]
    if low in _SES:
        return _SES[low]
    if low.endswith('ies') and len(low) > 4:
        return tok[:-3] + 'y'
    if low.endswith('zzes'):
        return tok[:-3]
    if low.endswith(('sses', 'xes', 'ches', 'shes')):
        return tok[:-2]
    if low.endswith('oes'):
        return tok[:-2] if low in _OES else tok[:-1]
    return tok[:-1]


def candidates(low):
    """Every plausible base form of a token.  Used for CONSERVATIVE duplicate detection:
    two tokens that could be inflections of the same word are treated as the same item."""
    c = {low}
    h = low.replace('-', '')
    c.add(h)
    for t in {low, h}:
        if t in IRREG_BACK:
            c |= IRREG_BACK[t]
        n = len(t)
        if n > 4 and t.endswith('ies'):
            c.add(t[:-3] + 'y')
        if n > 4 and t.endswith('ves'):
            c |= {t[:-3] + 'f', t[:-3] + 'fe', t[:-1]}
        if n > 3 and t.endswith('es'):
            c |= {t[:-2], t[:-1]}
        elif n > 3 and t.endswith('s') and not t.endswith('ss'):
            c.add(t[:-1])
        if n > 4 and t.endswith('ied'):
            c.add(t[:-3] + 'y')
        if n > 3 and t.endswith('ed'):
            b = t[:-2]
            if len(b) >= 2:
                c.add(b + 'e')
            if len(b) >= 3:
                c.add(b)
                if b[-1] == b[-2]:
                    c.add(b[:-1])
        if n > 4 and t.endswith('ing'):
            b = t[:-3]
            # a two-letter stem takes "+e" only where real verbs do (using -> use, icing -> ice,
            # owing -> owe, dying -> dye); this keeps bring / thing / cling from yielding "bre" / "the" / "cle"
            if len(b) >= 3 or (len(b) == 2 and (b[0] in 'aeiou' or b[1] == 'y')):
                c.add(b + 'e')
            if len(b) == 2 and b[1] == 'y':
                c.add(b[0] + 'ie')          # dying -> die, lying -> lie, tying -> tie
            if len(b) >= 3:
                c.add(b)
                if b[-1] == b[-2]:
                    c.add(b[:-1])
                if b.endswith('y'):
                    c.add(b[:-1] + 'ie')
    return c


def inflections(w, adj=False):
    """All regular + irregular inflected forms of a listed main word / family form."""
    w = w.lower()
    out = {w, w.replace('-', '')}
    out |= IRREG_FWD.get(w, set())
    if ' ' in w:
        return out
    if re.search(r'(s|x|z|ch|sh)$', w):
        out.add(w + 'es')
    elif re.search(r'[^aeiou]y$', w):
        out.add(w[:-1] + 'ies')
    else:
        out.add(w + 's')
    if w.endswith('o'):
        out.add(w + 'es')
    if w.endswith('fe'):
        out.add(w[:-2] + 'ves')
    elif w.endswith('f'):
        out.add(w[:-1] + 'ves')
    if w.endswith('e'):
        out |= {w + 'd', w[:-1] + 'ing'}
        if adj:
            out |= {w + 'r', w + 'st'}
    elif re.search(r'[^aeiou]y$', w):
        out |= {w[:-1] + 'ied', w + 'ing'}
        if adj:
            out |= {w[:-1] + 'ier', w[:-1] + 'iest'}
    else:
        out |= {w + 'ed', w + 'ing'}
        if adj:
            out |= {w + 'er', w + 'est'}
        if re.search(r'[^aeiou][aeiou][^aeiouwxy]$', w) or re.search(r'^[aeiou][^aeiouwxy]$', w):
            d = w + w[-1]
            out |= {d + 'ed', d + 'ing'}
            if adj:
                out |= {d + 'er', d + 'est'}
    if w.endswith('ie'):
        out.add(w[:-2] + 'ying')
    return out


# --- Porter2-style stemmer: used ONLY to build "related word" cross-references (never to block) ---
_V = 'aeiouy'


def _regions(w):
    m = re.match(r'^(gener|commun|arsen)', w)
    if m:
        r1 = m.end()
    else:
        m = re.search(r'[aeiouy][^aeiouy]', w)
        r1 = m.end() if m else len(w)
    m = re.search(r'[aeiouy][^aeiouy]', w[r1:])
    r2 = r1 + m.end() if m else len(w)
    return r1, r2


def _short_end(s):
    if len(s) >= 3 and s[-1] not in _V + 'wxY' and s[-2] in _V and s[-3] not in _V:
        return True
    return len(s) == 2 and s[0] in _V and s[1] not in _V


def stem(word):
    w = word.lower().replace('-', '').replace("'", '')
    if len(w) <= 2:
        return w
    w = re.sub(r'is(e|ed|es|ing|ation|ations|er|ers)$', r'iz\1', w) if len(w) > 6 else w
    exc = {'skis': 'ski', 'skies': 'sky', 'dying': 'die', 'lying': 'lie', 'tying': 'tie', 'idly': 'idl',
           'gently': 'gentl', 'ugly': 'ugli', 'early': 'earli', 'only': 'onli', 'singly': 'singl',
           'sky': 'sky', 'news': 'news', 'howe': 'howe', 'atlas': 'atlas', 'cosmos': 'cosmos',
           'bias': 'bias', 'andes': 'andes'}
    if w in exc:
        return exc[w]
    if w[0] == 'y':
        w = 'Y' + w[1:]
    w = re.sub(r'([aeiouy])y', r'\1Y', w)
    r1, r2 = _regions(w)
    if w.endswith('sses'):
        w = w[:-2]
    elif w.endswith(('ied', 'ies')):
        w = w[:-2] if len(w) > 4 else w[:-1]
    elif w.endswith(('us', 'ss')):
        pass
    elif w.endswith('s') and any(ch in _V for ch in w[:-2]):
        w = w[:-1]
    if w in ('inning', 'outing', 'canning', 'herring', 'earring', 'proceed', 'exceed', 'succeed'):
        return w
    done = False
    for suf in ('eedly', 'eed'):
        if w.endswith(suf):
            if len(w) - len(suf) >= r1:
                w = w[:-len(suf)] + 'ee'
            done = True
            break
    if not done:
        for suf in ('ingly', 'edly', 'ing', 'ed'):
            if w.endswith(suf):
                pre = w[:-len(suf)]
                if any(ch in _V for ch in pre):
                    w = pre
                    if w.endswith(('at', 'bl', 'iz')):
                        w += 'e'
                    elif len(w) > 1 and w[-1] == w[-2] and w[-1] in 'bdfgmnprt':
                        w = w[:-1]
                    elif _regions(w)[0] >= len(w) and _short_end(w):
                        w += 'e'
                break
    if len(w) > 2 and w[-1] in 'yY' and w[-2] not in _V:
        w = w[:-1] + 'i'
    r1, r2 = _regions(w)
    for suf, rep in (('ization', 'ize'), ('ational', 'ate'), ('fulness', 'ful'), ('ousness', 'ous'),
                     ('iveness', 'ive'), ('tional', 'tion'), ('biliti', 'ble'), ('lessli', 'less'),
                     ('entli', 'ent'), ('ation', 'ate'), ('alism', 'al'), ('aliti', 'al'), ('ousli', 'ous'),
                     ('iviti', 'ive'), ('fulli', 'ful'), ('enci', 'ence'), ('anci', 'ance'), ('abli', 'able'),
                     ('izer', 'ize'), ('ator', 'ate'), ('alli', 'al'), ('bli', 'ble'), ('ogi', 'og'),
                     ('li', '')):
        if w.endswith(suf):
            if len(w) - len(suf) >= r1:
                if suf == 'ogi' and not w.endswith('logi'):
                    break
                if suf == 'li' and (len(w) < 3 or w[-3] not in 'cdeghkmnrt'):
                    break
                w = w[:-len(suf)] + rep
            break
    r1, r2 = _regions(w)
    for suf, rep in (('ational', 'ate'), ('tional', 'tion'), ('alize', 'al'), ('icate', 'ic'), ('iciti', 'ic'),
                     ('ative', None), ('ical', 'ic'), ('ness', ''), ('ful', '')):
        if w.endswith(suf):
            if len(w) - len(suf) >= r1:
                if rep is None:
                    if len(w) - len(suf) >= r2:
                        w = w[:-len(suf)]
                else:
                    w = w[:-len(suf)] + rep
            break
    r1, r2 = _regions(w)
    for suf in ('ement', 'ance', 'ence', 'able', 'ible', 'ment', 'ant', 'ent', 'ism', 'ate', 'iti', 'ous',
                'ive', 'ize', 'ion', 'al', 'er', 'ic'):
        if w.endswith(suf):
            if len(w) - len(suf) >= r2:
                if suf == 'ion' and (len(w) < 4 or w[-4] not in 'st'):
                    break
                w = w[:-len(suf)]
            break
    r1, r2 = _regions(w)
    if w.endswith('e'):
        if len(w) - 1 >= r2 or (len(w) - 1 >= r1 and not _short_end(w[:-1])):
            w = w[:-1]
    elif w.endswith('ll') and len(w) - 1 >= r2:
        w = w[:-1]
    return w.lower()


_SUFFIXES = ('ically', 'ation', 'ition', 'ement', 'ness', 'ment', 'less', 'able', 'ible', 'tion', 'sion', 'ship',
             'hood', 'ance', 'ence', 'ical', 'ally', 'ful', 'ous', 'ive', 'ity', 'ist', 'ian', 'ion', 'dom',
             'ure', 'age', 'ism', 'ise', 'ize', 'ify', 'ial', 'ant', 'ent', 'ily', 'ing', 'ly', 'al', 'er',
             'or', 'ee', 'en', 'th', 'ic', 'ed', 'y', 'r')
_NEG = ('un', 'in', 'im', 'il', 'ir', 'dis', 'non', 'mis')
_FAMILY_GROUPS = """long length lengthen|strong strength strengthen|high height heighten|deep depth deepen
|wide width widen|broad breadth broaden|die death dead deadly|choose choice|sell sale|live life alive
|believe belief|prove proof|lose loss lost|think thought|fly flight|see sight|grow growth
|know knowledge|decide decision decisive|describe description|explain explanation|solve solution
|permit permission|admit admission|divide division|conclude conclusion|destroy destruction destructive
|receive reception receipt|succeed success successful|proud pride|hot heat|young youth|true truth
|wise wisdom|poor poverty|clear clarity clarify|able ability unable enable|vary variety various variable
|anxious anxiety|pronounce pronunciation|maintain maintenance|respond response|defend defence
|expand expansion|extend extension extent extensive|intend intention|attend attention attendance
|persuade persuasion|explode explosion|provide provision|revise revision|include inclusion inclusive
|exclude exclusion exclusive|evolve evolution|assume assumption|consume consumption consumer
|perceive perception|deceive deception|acquire acquisition|compete competition competitive competitor
|repeat repetition|recognise recognition|apply application applicant|analyse analysis analytical analyst
|emphasis emphasise|speak speech spoken|sing song|advise advice|practise practice|use usage useful
|marry marriage|fail failure|please pleasure pleasant|compare comparison|behave behaviour
|enter entrance entry|hunger hungry|anger angry|absent absence|present presence|patient patience
|silent silence|violent violence|science scientific scientist|art artist artistic|act action active activity actor
|day daily|fun funny|sun sunny|politics political politician|economy economic economics economist
|law lawyer legal|safe safety save|feed food|breathe breath|bathe bath|lend loan|give gift
|destroy destruction|produce product production productive|reduce reduction|introduce introduction
|simple simplify simplicity|just justice|free freedom|peace peaceful|danger dangerous|fame famous
|mystery mysterious|ambition ambitious|caution cautious|religion religious|nerve nervous|space spacious"""
FAMILY_GROUP = {}
for _i, _g in enumerate(_FAMILY_GROUPS.replace('\n', '').split('|')):
    for _w in _g.split():
        FAMILY_GROUP.setdefault(_w, set()).add(_i)


def soft_bases(lemma):
    """Possible related base words, found by stripping transparent affixes (cross-references only)."""
    w = lemma.lower().replace('-', '')
    out = set()
    for p in _NEG:
        if w.startswith(p) and len(w) - len(p) >= 4:
            out.add(w[len(p):])
    for suf in _SUFFIXES:
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            s = w[:-len(suf)]
            out |= {s, s + 'e', s + 'y'}
            if len(s) > 3 and s[-1] == s[-2]:
                out.add(s[:-1])
            if s.endswith('i'):
                out.add(s[:-1] + 'y')
            if suf in ('ation', 'ition', 'ion'):
                out.add(s + 'ate')
    out.discard(w)
    return out


# ------------------------------------------------------------------ text helpers
def tokenize(text):
    return TOKEN_RE.findall(text.replace('’', "'"))


_CONTR = {"can't": 'can', "won't": 'will', "shan't": 'shall'}


def strip_contr(tok):
    low = tok.lower()
    if low in _CONTR:
        return _CONTR[low]
    for suf in ("n't", "'s", "'re", "'ve", "'ll", "'d", "'m"):
        if low.endswith(suf) and len(low) > len(suf):
            return tok[:-len(suf)]
    return tok


def norm_expr(en):
    return ' '.join(t.lower() for t in tokenize(en))


def _cap(s, az):
    for i, ch in enumerate(s):
        if ch.isalpha():
            up = {'i': 'İ', 'ı': 'I'}.get(ch, ch.upper()) if az else ch.upper()
            return s[:i] + up + s[i + 1:]
        if ch not in '("\'«“‘[~ ':
            break
    return s


def en_cap(s):
    return _cap(s, False)


def az_cap(s):
    return _cap(s, True)


def wrap(text, first='', rest=None, width=WIDTH):
    rest = first if rest is None else rest
    return textwrap.fill(text, width=width, initial_indent=first, subsequent_indent=rest,
                         break_long_words=False, break_on_hyphens=False)


def wrap_list(words, indent='   ', width=WIDTH):
    return wrap(', '.join(words), indent, indent, width) if words else indent + '—'


def thousands(n):
    return format(n, ',')


AZ_OK = set("abcçdeəfgğhxıijkqlmnoöprsştuüvyzw" "ABCÇDEƏFGĞHXIİJKQLMNOÖPRSŞTUÜVYZW" "0123456789"
            " .,;:!?'\"()[]/-–—…%+&«»“”‘’*=<>→~№")
IPA_OK = set("ɑæɒɔəɜɪʊʌeiuaopbtdkɡfvθðszʃʒhmnŋlrjwxːˈˌ. ,;-")


# ------------------------------------------------------------------ data model
class Item(object):
    __slots__ = ('lemma', 'token', 'role', 'level', 'lesson', 'head', 'expr', 'expr_az', 'cat', 'az', 'seq')

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))

    def as_dict(self):
        return OrderedDict((k, getattr(self, k)) for k in self.__slots__ if getattr(self, k) is not None)


class Lesson(object):
    def __init__(self, level, unit, head, pos, ipa, az, src, line):
        self.level, self.unit, self.head, self.pos, self.ipa, self.az = level, unit, head, pos, ipa, az
        self.src, self.line = src, line
        self.forms = ''
        self.family = OrderedDict((c, []) for c, _ in CATS)
        self.exprs, self.sents, self.usage = [], [], []
        self.uid = ''
        self.new_items, self.db_before, self.db_after = [], 0, 0
        self.own = set()
        self.plan = False


class Unit(object):
    def __init__(self, level, en, az):
        self.level, self.en, self.az = level, en, az
        self.lessons = []
        self.no = 0


class DB(object):
    def __init__(self):
        self.structural = OrderedDict()   # lower form -> (group_en, forms_display, az)
        self.groups = []                  # (kind, en, az, [(forms, az)])
        self.items = []
        self.by_form = {}
        self.by_cand = defaultdict(list)
        self.expr_index = {}
        self.errors, self.warnings, self.notes = [], [], []
        self.distinct = {}                # frozenset(pair) -> reason
        self.distinct_used = set()
        self.lemma_over = {}
        self.not_related = set()
        self.related = set()              # confirmed family links (source/related.txt)
        self.unreviewed_links = set()     # stem-based candidates not yet confirmed or rejected
        self.reserved = {}                # lower form -> (HEAD, level)
        self.roadmap = OrderedDict((l, []) for l in LEVELS)   # level -> [(HEAD, [family])]
        self.units = OrderedDict((l, []) for l in LEVELS)
        self.lessons = []
        self.lesson_by_head = {}

    # ---- registration with global duplicate detection
    def register(self, token, role, L, expr=None, expr_az=None, cat=None, az=None, err=None):
        low = token.lower()
        lemma = token if role != 'COLLOCATE' else self.lemma_over.get(low, lemma_of(token))
        ll = lemma.lower()
        keys = {low, ll, low.replace('-', ''), ll.replace('-', '')}
        cands = set()
        for k in keys:
            cands |= candidates(k)
        hits = OrderedDict()
        for k in sorted(keys):
            for it in self.by_cand.get(k, ()):
                hits[id(it)] = it
        for c in sorted(cands):
            it = self.by_form.get(c)
            if it is not None:
                hits[id(it)] = it
            # two different inflected forms that share a possible base (hidden / hiding -> hide)
            for it in self.by_cand.get(c, ()):
                hits[id(it)] = it
        real = []
        for it in hits.values():
            if it.lemma.lower() != ll:
                pair = frozenset((it.lemma.lower(), ll))
                if pair in self.distinct:
                    self.distinct_used.add(pair)
                    continue
                if it.lesson == L.uid and it.role in ('MAIN', 'FAMILY') and role in ('MAIN', 'FAMILY'):
                    continue
            real.append(it)
        if real:
            it = real[0]
            where = '%s %s' % (it.lesson, it.head) + (' "%s"' % it.expr if it.expr else ' [%s]' % it.role.lower())
            err("DUPLICATE '%s' (%s) - already taught as '%s' in %s" % (token, role.lower(), it.lemma, where))
            return None
        for c in sorted(cands | keys):
            r = self.reserved.get(c)
            if r and r[0].lower() != L.head.lower():
                if frozenset((c, ll)) in self.distinct or frozenset((r[0].lower(), ll)) in self.distinct:
                    continue
                err("RESERVED '%s' - belongs to the planned main word %s (%s)" % (token, r[0], r[1]))
                return None
        item = Item(lemma=lemma, token=token, role=role, level=L.level, lesson=L.uid, head=L.head,
                    expr=expr, expr_az=expr_az, cat=cat, az=az, seq=len(self.items))
        self.items.append(item)
        for k in keys:
            self.by_form.setdefault(k, item)
        for c in cands:
            self.by_cand[c].append(item)
        return item


# ------------------------------------------------------------------ parsing
def read_lines(path):
    with open(path, encoding='utf-8') as f:
        for n, raw in enumerate(f, 1):
            s = raw.strip()
            if s and not s.startswith('//'):
                yield n, s


def load_aux(db):
    p = os.path.join(SRC, 'distinct_lexemes.txt')
    if os.path.exists(p):
        for n, s in read_lines(p):
            body, _, reason = s.partition('#')
            a, _, b = body.partition('|')
            if a.strip() and b.strip():
                db.distinct[frozenset((a.strip().lower(), b.strip().lower()))] = reason.strip()
    p = os.path.join(SRC, 'lemma_overrides.txt')
    if os.path.exists(p):
        for n, s in read_lines(p):
            a, _, b = s.partition('#')[0].partition('=')
            if a.strip() and b.strip():
                db.lemma_over[a.strip().lower()] = b.strip()
    p = os.path.join(SRC, 'not_related.txt')
    if os.path.exists(p):
        for n, s in read_lines(p):
            a, _, b = s.partition('#')[0].partition('|')
            if a.strip() and b.strip():
                db.not_related.add(frozenset((a.strip().lower(), b.strip().lower())))
    p = os.path.join(SRC, 'related.txt')
    if os.path.exists(p):
        for n, s in read_lines(p):
            a, _, b = s.partition('#')[0].partition('|')
            if a.strip() and b.strip():
                db.related.add(frozenset((a.strip().lower(), b.strip().lower())))
    p = os.path.join(SRC, 'roadmap.txt')
    if os.path.exists(p):
        for n, s in read_lines(p):
            lvl, _, rest = s.partition(':')
            lvl = lvl.strip()
            if lvl not in LEVELS:
                db.errors.append('roadmap.txt:%d unknown level %r' % (n, lvl))
                continue
            for ent in rest.split(';'):
                ent = ent.strip()
                if not ent:
                    continue
                head, _, fam = ent.partition('+')
                head = head.strip()
                fams = [x.strip() for x in fam.split(',') if x.strip()]
                db.roadmap[lvl].append((head, fams))
                for t in tokenize(head):
                    db.reserved.setdefault(t.lower(), (head, lvl))
                for x in fams:
                    db.reserved.setdefault(x.lower(), (head, lvl))


def load_foundation(db):
    p = os.path.join(SRC, '00_foundation.txt')
    if not os.path.exists(p):
        return
    cur = None
    L0 = Lesson('A1', None, 'FOUNDATION', '', '', '', p, 0)
    L0.uid = 'A1-000'
    for n, s in read_lines(p):
        if s.startswith('#'):
            parts = [x.strip() for x in s[1:].split('|')]
            cur = (parts[0].upper(), parts[1], parts[2], [])
            db.groups.append(cur)
            continue
        forms, _, az = s.partition('=')
        forms = [x.strip() for x in forms.split(',') if x.strip()]
        az = az.strip()
        cur[3].append((forms, az))
        for f in forms:
            if cur[0] == 'STRUCTURAL':
                for t in tokenize(f):
                    db.structural.setdefault(t.lower(), (cur[1], ', '.join(forms), az))
            else:
                db.register(f, 'REFERENCE', L0, az=az,
                            err=lambda m, n=n: db.errors.append('00_foundation.txt:%d %s' % (n, m)))
    db.reserved = {k: v for k, v in db.reserved.items() if k not in db.structural}


def load_lessons(db):
    for lvl in LEVELS:
        d = os.path.join(SRC, lvl)
        if not os.path.isdir(d):
            continue
        unit, cur = None, None
        for fn in sorted(os.listdir(d)):
            if not fn.endswith('.txt'):
                continue
            path = os.path.join(d, fn)
            rel = '%s/%s' % (lvl, fn)
            for n, s in read_lines(path):
                try:
                    if s.startswith('##'):
                        parts = [x.strip() for x in s[2:].split('|')]
                        unit = Unit(lvl, parts[0], parts[1] if len(parts) > 1 else '')
                        db.units[lvl].append(unit)
                        unit.no = len(db.units[lvl])
                    elif s.startswith('@'):
                        parts = [x.strip() for x in s[1:].split('|')]
                        if len(parts) != 4:
                            raise ValueError('header needs: @ WORD | pos | ipa | azerbaijani')
                        if unit is None:
                            raise ValueError('lesson before any "## unit" header')
                        cur = Lesson(lvl, unit, parts[0], parts[1], parts[2].strip('/'), parts[3], rel, n)
                        unit.lessons.append(cur)
                        db.lessons.append(cur)
                    elif s.startswith('forms:'):
                        cur.forms = s[6:].strip()
                    elif re.match(r'^(n|v|adj|adv):', s):
                        cat, _, rest = s.partition(':')
                        for chunk in rest.split(';'):
                            if chunk.strip() and chunk.strip() != '-':
                                form, _, az = chunk.partition('=')
                                if not az.strip():
                                    raise ValueError('family form without translation: %r' % chunk)
                                cur.family[cat].append((form.strip(), az.strip()))
                    elif s.startswith(('- ', '~ ')):
                        body, _, note = s[2:].partition('::')
                        en, _, az = body.partition('=')
                        if not az.strip():
                            raise ValueError('expression without translation')
                        cur.exprs.append((en.strip(), az.strip(), note.strip(), s[0] == '~'))
                    elif s.startswith('> '):
                        en, sep, az = s[2:].partition(' = ')
                        if not sep:
                            raise ValueError('sentence needs " = " between English and Azerbaijani')
                        cur.sents.append((en.strip(), az.strip()))
                    elif s.startswith('! '):
                        cur.usage.append(s[2:].strip())
                    else:
                        raise ValueError('unrecognised line')
                except Exception as e:      # noqa
                    db.errors.append('%s:%d %s  | %s' % (rel, n, e, s[:60]))
    for lvl in LEVELS:
        k = 0
        for u in db.units[lvl]:
            for L in u.lessons:
                k += 1
                L.uid = '%s-%03d' % (lvl, k)


# ------------------------------------------------------------------ validation
def process_lesson(db, L):
    def err(msg):
        db.errors.append('%s %s: %s' % (L.uid, L.head, msg))

    def warn(msg):
        db.warnings.append('%s %s: %s' % (L.uid, L.head, msg))

    L.db_before = len(db.items)
    start = len(db.items)
    if L.head.lower() in db.lesson_by_head:
        err('main word already has a lesson (%s)' % db.lesson_by_head[L.head.lower()].uid)
    db.lesson_by_head[L.head.lower()] = L
    is_adj = bool(re.search(r'adj|adv', L.pos))
    own = set()
    for t in tokenize(L.head):
        b = strip_contr(t)
        if b.lower() in db.structural:
            continue
        db.register(b if len(tokenize(L.head)) > 1 else L.head, 'MAIN', L, az=L.az, cat=L.pos, err=err)
        own |= inflections(b, is_adj)
    if not own:
        err('main word consists only of structural words')
    for t in tokenize(L.forms):
        own.add(t.lower())
    for cat, _ in CATS:
        seen = set()
        for form, az in L.family[cat]:
            if form.lower() in seen:
                err('family form listed twice: %s' % form)
            seen.add(form.lower())
            if form.lower() in db.structural:
                err("family form '%s' is a structural word" % form)
                continue
            db.register(form, 'FAMILY', L, az=az, cat=cat, err=err)
            own |= inflections(form, cat in ('adj', 'adv'))
    L.own = own
    lesson_new = set()
    for (en, az, note, related) in L.exprs:
        ne = norm_expr(en)
        if ne in db.expr_index:
            err('DUPLICATE EXPRESSION "%s" (already in %s)' % (en, db.expr_index[ne]))
        db.expr_index[ne] = L.uid
        has_own, new_here = False, 0
        for t in tokenize(en):
            b = strip_contr(t)
            low = b.lower()
            if low in db.structural:
                continue
            if low in own or low.replace('-', '') in own:
                has_own = True
                continue
            if '-' in low:
                parts = low.split('-')
                if any(p in own for p in parts):
                    has_own = True
                if all(p in own or p in db.structural for p in parts):
                    pass
            it = db.register(b, 'COLLOCATE', L, expr=en, expr_az=az, err=err)
            if it is not None:
                new_here += 1
                lesson_new |= candidates(low) | {it.lemma.lower()}
        if related and new_here == 0:
            err('related expression "~ %s" introduces no new word' % en)
        if not related and not has_own:
            err('expression "%s" does not contain the main word or a family form (prefix with ~ if intended)' % en)
    L.new_items = db.items[start:]
    L.db_after = len(db.items)
    if L.plan:
        return
    if not (7 <= len(L.exprs) <= 8):
        err('needs 7-8 expressions, has %d' % len(L.exprs))
    if not (3 <= len(L.sents) <= 5):
        err('needs 3-5 example sentences, has %d' % len(L.sents))
    if not L.usage:
        err('usage explanation missing')
    if not L.ipa or not L.az or not L.pos:
        err('header field missing')
    bad = set(re.sub(r'\([^)]*\)', '', L.ipa)) - IPA_OK
    if bad:
        err('unexpected IPA characters: %s' % ' '.join(sorted(bad)))
    for (en, az, note, related) in L.exprs:
        if not note:
            err('expression "%s" has no usage note' % en)
        b = set(az) - AZ_OK
        if b:
            warn('odd characters in translation of "%s": %s' % (en, ' '.join(sorted(b))))
    for i, (en, az) in enumerate(L.sents, 1):
        toks = {strip_contr(t).lower() for t in tokenize(en)}
        if not (toks & own) and not (toks & lesson_new):
            warn('example sentence %d uses neither the main word nor a lesson expression' % i)
        b = set(az) - AZ_OK
        if b:
            warn('odd characters in sentence %d translation: %s' % (i, ' '.join(sorted(b))))
        if en[-1] not in '.!?"\'' or az[-1] not in '.!?"\'':
            warn('example sentence %d lacks final punctuation' % i)


def build_db(plan_lessons=None):
    db = DB()
    load_aux(db)
    load_foundation(db)
    load_lessons(db)
    for L in db.lessons:
        process_lesson(db, L)
    done = {L.head.lower() for L in db.lessons}
    for lvl in LEVELS:
        for head, fams in db.roadmap[lvl]:
            if head.lower() in done and db.lesson_by_head[head.lower()].level != lvl:
                db.warnings.append('roadmap: %s planned for %s but taught in %s'
                                   % (head, lvl, db.lesson_by_head[head.lower()].level))
    for pair in db.distinct:
        if pair not in db.distinct_used:
            db.notes.append('distinct_lexemes.txt: pair not (yet) needed: %s' % ' | '.join(sorted(pair)))
    return db


# ------------------------------------------------------------------ cross references
def cross_refs(db):
    """item.seq -> related items taught in OTHER lessons (same family, different form).
    A shared stem only PROPOSES a link.  A link is shown to the learner only when the pair is confirmed in
    source/related.txt; rejected pairs live in source/not_related.txt; everything else is reported as
    "not yet reviewed" in the QA report, never in the lesson files."""
    by_lemma = {}
    by_stem = defaultdict(list)
    for it in db.items:
        by_lemma.setdefault(it.lemma.lower(), it)
        by_stem[stem(it.lemma)].append(it)
    rel = defaultdict(dict)
    db.unreviewed_links = set()

    def link(a, b, confirmed=False):
        if a is b or a.lesson == b.lesson:
            return
        pair = frozenset((a.lemma.lower(), b.lemma.lower()))
        if len(pair) < 2 or pair in db.not_related:
            return
        if not confirmed and pair not in db.related:
            db.unreviewed_links.add(pair)
            return
        rel[a.seq][b.seq] = b
        rel[b.seq][a.seq] = a

    for group in by_stem.values():
        for a in group:
            for b in group:
                if a.seq < b.seq:
                    link(a, b)
    for it in db.items:
        low = it.lemma.lower()
        for base in soft_bases(low):
            o = by_lemma.get(base)
            if o is not None:
                link(it, o)
        for g in FAMILY_GROUP.get(low, ()):
            for other, gs in FAMILY_GROUP.items():
                if g in gs and other != low and other in by_lemma:
                    link(it, by_lemma[other])
    for pair in db.related:                      # confirmed pairs that the stemmer did not propose
        x, y = sorted(pair)
        if x in by_lemma and y in by_lemma:
            link(by_lemma[x], by_lemma[y], confirmed=True)
    return rel


# ------------------------------------------------------------------ optional QA against open reference data
def load_refs():
    refs = {'cefr': {}, 'ipa': defaultdict(set)}
    try:
        import csv
        for fn in ('olp-en-cefrj/cefrj-vocabulary-profile-1.5.csv',
                   'olp-en-cefrj/octanove-vocabulary-profile-c1c2-1.0.csv'):
            p = os.path.join(REF, fn)
            if os.path.exists(p):
                with open(p, encoding='utf-8') as f:
                    for row in csv.DictReader(f):
                        lv = LEVELS.index(row['CEFR']) if row['CEFR'] in LEVELS else None
                        if lv is None:
                            continue
                        for hw in row['headword'].split('/'):
                            hw = hw.strip().lower()
                            if hw and (hw not in refs['cefr'] or lv < refs['cefr'][hw]):
                                refs['cefr'][hw] = lv
        p = os.path.join(REF, 'Britfone/britfone.main.3.0.1.csv')
        if os.path.exists(p):
            with open(p, encoding='utf-8') as f:
                for line in f:
                    w, _, ph = line.partition(',')
                    refs['ipa'][re.sub(r'\(\d+\)$', '', w.strip()).lower()].add(ph.strip().replace(' ', ''))
        p = os.path.join(REF, 'ipa-dict/data/en_UK.txt')
        if os.path.exists(p):
            with open(p, encoding='utf-8') as f:
                for line in f:
                    w, _, ph = line.rstrip('\n').partition('\t')
                    if w.lower() not in refs['ipa']:
                        for v in ph.split(','):
                            refs['ipa'][w.lower() + '\t'].add(v.strip().strip('/'))
    except Exception as e:   # noqa
        sys.stderr.write('reference data not loaded: %s\n' % e)
    return refs


_TURNED_A = 'ʌ'      # what the reference list in use means by the symbol ɐ (set per source in qa_report)


def _ipa_clean(s):
    """Notation-only normalisation; stress marks are kept."""
    s = re.sub(r'\([^)]*\)', '', s).replace('/', '').replace(' ', '').replace('.', '')
    for a, b in (('ɹ', 'r'), ('g', 'ɡ'), ('ɛə', 'eə'), ('ɛ', 'e'), ('ɐ', _TURNED_A)):
        s = s.replace(a, b)
    return s


def _ipa_norm(s):
    """Segments only: stress marks removed first, then syllabic consonants unified (əl = l ...)."""
    s = _ipa_clean(s).replace('ˈ', '').replace('ˌ', '')
    for a, b in (('əl', 'l'), ('ən', 'n'), ('əm', 'm')):
        s = s.replace(a, b)
    return s


def _ipa_broad(s):
    """Broad form used to recognise transcriptions that differ ONLY in weak-vowel notation, where
    dictionaries legitimately disagree (happy-vowel i/ɪ, u/ʊ, unstressed ɪ/ə, tj/tʃ, dj/dʒ)."""
    s = _ipa_norm(s)
    s = re.sub('uː(?=[ɑæɒɔəɜɪʊʌeiuao])', 'u', s)     # weak u before a vowel (fluctuate, situation)
    s = re.sub('iː(?=[ɑæɒɔəɜɪʊʌeiuao])', 'i', s)     # weak i before a vowel (alleviate, create)
    s = re.sub('i(?!ː)', 'ɪ', s)
    s = re.sub('u(?!ː)', 'ʊ', s)
    s = s.replace('dj', 'dʒ').replace('tj', 'tʃ')
    for k, d in enumerate(('ɪə', 'eə', 'ʊə', 'əʊ', 'aɪ', 'eɪ', 'ɔɪ', 'aʊ')):
        s = s.replace(d, str(k))
    return s.replace('ə', 'ɪ')


def _stress_pos(s):
    """Number of vowel nuclei before the primary stress mark (independent of where a dictionary
    puts the mark inside the consonant cluster)."""
    s = _ipa_clean(s)
    n, prev = 0, False
    for ch in s:
        if ch == 'ˈ':
            return n
        v = ch in 'ɑæɒɔəɜɪʊʌeiuaoː'
        if v and not prev:
            n += 1
        prev = v
    return 0


def qa_report(db, refs):
    out = []
    cefr = refs['cefr']
    if cefr:
        out.append('== MAIN WORD LEVEL vs open reference lists (CEFR-J A1-B2, Octanove C1-C2) ==')
        same = near = far = unk = 0
        for L in db.lessons:
            r = cefr.get(L.head.lower())
            if r is None:
                unk += 1
                continue
            d = r - LEVELS.index(L.level)
            if d == 0:
                same += 1
            elif abs(d) == 1:
                near += 1
                out.append('  near  %s %-14s here %s, reference %s' % (L.uid, L.head, L.level, LEVELS[r]))
            else:
                far += 1
                out.append('  REVIEW %s %-14s here %s, reference %s' % (L.uid, L.head, L.level, LEVELS[r]))
        out.append('  summary: same=%d, one level apart=%d, two or more apart=%d, not in reference=%d'
                   % (same, near, far, unk))
        out.append('')
        out.append('== COLLOCATES two or more levels ABOVE their lesson level ==')
        k = 0
        for it in db.items:
            if it.role == 'COLLOCATE':
                r = cefr.get(it.lemma.lower())
                if r is not None and r - LEVELS.index(it.level) >= 2:
                    k += 1
                    out.append('  %s %-12s %-16s ref %s  "%s"' % (it.lesson, it.head, it.lemma, LEVELS[r], it.expr))
        out.append('  count=%d' % k)
        out.append('')
        out.append('== COVERAGE of the reference lists by this database ==')
        known = set(db.structural)
        for it in db.items:
            known.add(it.lemma.lower())
            known.add(it.token.lower())
        tot = defaultdict(int)
        cov = defaultdict(int)
        for w, lv in cefr.items():
            if ' ' in w or not w.isalpha():
                continue
            tot[lv] += 1
            if w in known or (candidates(w) & known):
                cov[lv] += 1
        for i, lv in enumerate(LEVELS):
            if tot[i]:
                out.append('  %s: %d of %d reference headwords (%.0f%%)' % (lv, cov[i], tot[i], 100.0 * cov[i] / tot[i]))
        out.append('')
    out.append('== WORD-FAMILY LINK CANDIDATES not yet reviewed (shared stem; shown to the learner only after review) ==')
    for pair in sorted(db.unreviewed_links, key=lambda p: sorted(p)):
        out.append('  ' + ' | '.join(sorted(pair)))
    out.append('  count=%d   (move each pair to source/related.txt or source/not_related.txt)' % len(db.unreviewed_links))
    out.append('')
    if refs['ipa']:
        out.append('== IPA cross-check of main words (Britfone; fallback ipa-dict en_UK) ==')
        cnt = {'Britfone': [0, 0, 0], 'fallback': [0, 0, 0]}
        miss = 0
        reviewed = {}
        rp = os.path.join(SRC, 'ipa_reviewed.txt')
        if os.path.exists(rp):
            for n, line in read_lines(rp):
                w, _, why = line.partition('|')
                if w.strip():
                    reviewed[w.strip().lower()] = why.strip()
        nrev = 0
        for L in db.lessons:
            w = L.head.lower()
            if ' ' in w:
                continue
            src = 'Britfone'
            theirs = refs['ipa'].get(w)
            if not theirs:
                src = 'fallback'
                theirs = refs['ipa'].get(w + '\t')
            if not theirs:
                miss += 1
                continue
            # Britfone writes the STRUT vowel as ɐ; the fallback list uses ɐ for an unstressed schwa
            global _TURNED_A
            _TURNED_A = 'ʌ' if src == 'Britfone' else 'ə'
            mine = [x for x in re.split(r'[,;]', L.ipa) if x.strip()]
            mn = {_ipa_norm(x) for x in mine}
            tn = {_ipa_norm(x) for x in theirs}
            st_ok = any(_stress_pos(a) == _stress_pos(b) for a in mine for b in theirs)
            if mn & tn and st_ok:
                cnt[src][0] += 1
            elif st_ok and ({_ipa_broad(x) for x in mine} & {_ipa_broad(x) for x in theirs}):
                cnt[src][1] += 1
                out.append('  variant %s %-14s here /%s/   %s: %s' % (L.uid, L.head, L.ipa, src,
                                                                     ' | '.join(sorted(theirs))))
            elif src == 'fallback' and w in reviewed:
                nrev += 1
                out.append('  reviewed %s %-14s here /%s/   fallback: %s   (%s)'
                           % (L.uid, L.head, L.ipa, ' | '.join(sorted(theirs)), reviewed[w]))
            else:
                cnt[src][2] += 1
                out.append('  DIFFER  %s %-14s here /%s/   %s: %s%s' % (L.uid, L.head, L.ipa, src,
                                                                       ' | '.join(sorted(theirs)),
                                                                       '' if st_ok else '   [STRESS]'))
        out.append('  "variant" = same sounds and stress, different notation of a weak vowel (i/ɪ, u/ʊ, ɪ/ə, tj/tʃ, dj/dʒ).')
        out.append('  "fallback" = ipa-dict en_UK, a second open list used only for words that Britfone does not contain.')
        out.append('  Both lists are open community resources and can contain errors themselves: a DIFFER line is a prompt')
        out.append('  to re-check the word in a printed dictionary, not proof of an error.')
        out.append('  summary: IPA vs Britfone 3.0.1: agree=%d, notation variants=%d, differ=%d'
                   % tuple(cnt['Britfone']))
        out.append('  "reviewed" = differs from the fallback list, re-checked by the author and kept; the reason is given')
        out.append('  in source/ipa_reviewed.txt (an author\'s judgement, not a machine verification).')
        out.append('  summary: IPA vs fallback list (words missing from Britfone): agree=%d, notation variants=%d, '
                   'differ=%d, differ but reviewed by the author=%d; in neither list=%d'
                   % (tuple(cnt['fallback']) + (nrev, miss)))
    return out


# ------------------------------------------------------------------ rendering
RULE = '=' * WIDTH
THIN = '-' * WIDTH
TODAY = datetime.date.today().isoformat()

LEGEND = [
    'HOW TO READ A LESSON  /  DƏRSİ NECƏ OXUMALI',
    '  A. MAIN WORD ............ Əsas söz: yazılışı, Azərbaycanca mənası, nitq hissəsi, Britaniya tələffüzü (IPA), səviyyəsi',
    '  B. WORD FAMILY .......... Söz ailəsi: eyni kökdən yaranan isim, fel, sifət və zərf formaları',
    '  C. RELATED EXPRESSIONS .. Əlaqəli ifadələr: əsas sözlə işlənən 7–8 təbii söz birləşməsi (hər biri yeni söz öyrədir)',
    '  D. EXAMPLE SENTENCES .... Nümunə cümlələr: ifadələrin cümlədə işlənməsi və Azərbaycanca tərcüməsi',
    '  E. USAGE EXPLANATION .... İşlənmə izahı: oxşar ifadələrin fərqi, qrammatik qəliblər, üslub',
    '  DATABASE UPDATE ......... Bu dərsdə bazaya əlavə olunan yeni sözlər və təkrar yoxlamasının nəticəsi',
    '',
    '  sb = somebody (kimsə)      sth = something (nəsə)      one\'s = my / your / his / her ... (öz)',
    '  An expression marked [related] belongs to the same topic but does not contain the main word itself.',
    '  [related] işarəli ifadə eyni mövzuya aiddir, lakin əsas sözün özünü ehtiva etmir.',
    '',
    'THE NO-REPETITION RULE  /  TƏKRARSIZLIQ QAYDASI',
    '  Every English word is taught exactly ONCE in the whole A1–C2 system: as a main word, as a word-family',
    '  form, or as the new word inside one expression. Only grammar words (a, the, of, to, be, have, do ...)',
    '  listed in A1 "Section 0" may recur inside expressions. Example sentences may recycle known words.',
    '  Hər bir ingilis sözü bütün sistemdə (A1–C2) yalnız BİR dəfə öyrədilir. Yalnız A1 faylının',
    '  "Section 0" bölməsindəki qrammatik sözlər ifadələrin içində təkrarlana bilər.',
]


def note_lang(level):
    return 'Azerbaijani' if level in ('A1', 'A2') else 'English'


def render_lesson(db, L, rel):
    o = []
    o.append(RULE)
    o.append('LESSON %s   |   UNIT %d: %s' % (L.uid, L.unit.no, L.unit.en))
    o.append(RULE)
    o.append('MAIN WORD: %s' % L.head.upper())
    o.append('Azerbaijani: %s' % az_cap(L.az))
    o.append('')
    o.append('A. MAIN WORD')
    o.append('   English spelling ....... %s' % L.head.lower() if L.head.isupper() else
             '   English spelling ....... %s' % L.head)
    o.append(wrap('Azerbaijani meaning .... %s' % L.az, '   ', ' ' * 27))
    o.append('   Part of speech ......... %s' % L.pos)
    if L.forms:
        o.append(wrap('Key forms .............. %s' % L.forms, '   ', ' ' * 27))
    o.append('   British English IPA .... /%s/' % L.ipa if not re.search(r'[,;(]', L.ipa) else
             '   British English IPA .... %s' % ', '.join('/%s/' % re.sub(r'\s*(\([^)]*\))', r'/ \1', x.strip()).rstrip('/')
                                                           if '(' in x else '/%s/' % x.strip()
                                                           for x in re.split(r'[,;]', L.ipa)).replace('/ (', '/ ('))
    o.append('   CEFR level ............. %s (%s)' % (L.level, LEVEL_NAME[L.level]))
    ref = getattr(db, 'ref_levels', {}).get(L.head.lower())
    if ref in LEVELS and ref != L.level:
        if LEVELS.index(ref) < LEVELS.index(L.level):
            note = ('The headword on its own is listed at %s in the open reference wordlist; this lesson is %s '
                    'because the expressions built on it are %s material.' % (ref, L.level, L.level))
        else:
            note = ('The open reference wordlist places this headword at %s; it is taught here at %s because '
                    'the expressions chosen for it are %s material (wordlists differ).' % (ref, L.level, L.level))
        o.append(wrap('Level note ............. ' + note, '   ', ' ' * 27))
    o.append('')
    o.append('B. WORD FAMILY')
    posmap = {'n': 'noun', 'v': 'verb', 'adj': 'adjective', 'adv': 'adverb'}
    for cat, label in CATS:
        parts = []
        if re.search(r'\b%s\b' % posmap[cat], L.pos):
            parts.append('%s (main word)' % L.head.lower() if L.head.isupper() else '%s (main word)' % L.head)
        parts += ['%s — %s' % (f, a) for f, a in L.family[cat]]
        label_d = (label + ' ').ljust(19, '.')
        o.append(wrap('%s %s' % (label_d, '; '.join(parts) if parts else '—'), '   ', ' ' * 23))
    fam_items = [it for it in L.new_items if it.role in ('MAIN', 'FAMILY')]
    seen, links = set(), []
    for it in fam_items:
        for other in sorted(rel.get(it.seq, {}).values(), key=lambda x: x.seq):
            if other.seq not in seen and other.role != 'REFERENCE':
                seen.add(other.seq)
                links.append('%s (%s, %s)' % (other.lemma, other.lesson, other.head))
    if links:
        o.append(wrap('Related words taught in other lessons (not repeated here): ' + '; '.join(links),
                      '   ', '      '))
    o.append('')
    o.append('C. RELATED EXPRESSIONS')
    for i, (en, az, note, related) in enumerate(L.exprs, 1):
        tag = '  [related]' if related else ''
        o.append(wrap('%d. %s — %s%s' % (i, en_cap(en), az_cap(az), tag), '   ', '      '))
        o.append(wrap('Usage: %s' % note, '      ', '             '))
    o.append('')
    o.append('D. NATURAL EXAMPLE SENTENCES')
    for i, (en, az) in enumerate(L.sents, 1):
        o.append(wrap('%d. %s' % (i, en), '   ', '      '))
        o.append(wrap('→ %s' % az, '      ', '        '))
    o.append('')
    o.append('E. USAGE EXPLANATION')
    for para in L.usage:
        o.append(wrap(para, '   ', '   '))
    o.append('')
    o.append('DATABASE UPDATE')
    names = []
    for it in L.new_items:
        names.append(it.lemma + (' [main]' if it.role == 'MAIN' else ' [family]' if it.role == 'FAMILY' else ''))
    o.append(wrap('New vocabulary registered in this lesson (%d): %s' % (len(names), ', '.join(names)),
                  '   ', '      '))
    o.append('   Duplicate check: PASSED — none of these items appears anywhere else in the system '
             '(%s → %s items).' % (thousands(L.db_before), thousands(L.db_after)))
    o.append('')
    return o


def render_foundation(db):
    o = [RULE, 'SECTION 0 — FOUNDATION: STRUCTURAL WORDS AND REFERENCE SETS', RULE]
    o.append(wrap('These are the grammar words of English (articles, pronouns, prepositions and particles, '
                  'conjunctions, auxiliary and modal verbs, quantifiers, numerals). They are taught ONCE, here. '
                  'Because no natural phrase can be built without them, they are the ONLY words that may appear '
                  'again inside the expressions of later lessons. They are never presented as new vocabulary again.'))
    o.append(wrap('Bunlar ingilis dilinin qrammatik sözləridir (artikllar, əvəzliklər, sözönülər, bağlayıcılar, '
                  'köməkçi və modal fellər, miqdar bildirən sözlər, saylar). Onlar yalnız BİR dəfə — burada — '
                  'öyrədilir. Bu sözlərsiz təbii ifadə qurmaq mümkün olmadığı üçün yalnız onlar sonrakı '
                  'dərslərin ifadələrində təkrar işlənə bilər.'))
    o.append('')
    for kind, en, az, rows in db.groups:
        o.append('%s  /  %s%s' % (en.upper(), az, '' if kind == 'STRUCTURAL' else
                                 '   [reference set: taught once, NOT reusable in expressions]'))
        o.append(THIN)
        for forms, a in rows:
            o.append(wrap('%-28s — %s' % (', '.join(forms), a), '   ', ' ' * 34))
        o.append('')
    return o


def level_items(db, lvl):
    return [it for it in db.items if it.level == lvl and it.role != 'REFERENCE']


def render_level_files(db, rel):
    files = OrderedDict()
    cum = 0
    cum_by_level = {}
    for lvl in LEVELS:
        units = db.units[lvl]
        lessons = [L for u in units for L in u.lessons]
        parts, cur, n = [], [], 0
        for u in units:
            if cur and n + len(u.lessons) > MAX_LESSONS_PER_FILE:
                parts.append(cur)
                cur, n = [], 0
            cur.append(u)
            n += len(u.lessons)
        parts.append(cur)
        items = level_items(db, lvl)
        cum += len(items) + (sum(1 for it in db.items if it.role == 'REFERENCE') if lvl == 'A1' else 0)
        cum_by_level[lvl] = cum
        for pi, punits in enumerate(parts, 1):
            name = '%s_VOCABULARY.txt' % lvl if pi == 1 else '%s_VOCABULARY_PART_%02d.txt' % (lvl, pi)
            o = [RULE, 'ENGLISH VOCABULARY MASTER SYSTEM — A1 TO C2   (English → Azerbaijani)',
                 'LEVEL %s — %s  /  %s' % (lvl, LEVEL_NAME[lvl].upper(), LEVEL_AZ[lvl]), RULE]
            o.append('File: %s   |   Part %d of %d   |   Generated: %s' % (name, pi, len(parts), TODAY))
            pl = [L for u in punits for L in u.lessons]
            o.append('Lessons in this file: %d   |   Expressions: %d   |   Example sentences: %d'
                     % (len(pl), sum(len(L.exprs) for L in pl), sum(len(L.sents) for L in pl)))
            o.append('New vocabulary items introduced at level %s: %s   |   Language of usage notes: %s'
                     % (lvl, thousands(len(items)), note_lang(lvl)))
            o.append('')
            o += LEGEND
            o.append('')
            o.append('CONTENTS OF THIS FILE')
            if lvl == 'A1' and pi == 1 and db.groups:
                o.append('   SECTION 0 — Foundation: structural words and reference sets')
            for u in punits:
                o.append('   UNIT %d — %s  /  %s' % (u.no, u.en, u.az))
                o.append(wrap(', '.join('%s %s' % (L.uid, L.head) for L in u.lessons), '      ', '      '))
            o.append('')
            if lvl == 'A1' and pi == 1 and db.groups:
                o += render_foundation(db)
            for u in punits:
                o.append('')
                o.append('#' * WIDTH)
                o.append('#  UNIT %d — %s' % (u.no, u.en.upper()))
                o.append('#  %s' % u.az)
                o.append('#' * WIDTH)
                o.append('')
                for L in u.lessons:
                    o += render_lesson(db, L, rel)
                uitems = [it for L in u.lessons for it in L.new_items]
                o.append(THIN)
                o.append('UPDATED VOCABULARY INDEX — after UNIT %d (%s)' % (u.no, u.en))
                o.append(THIN)
                o.append('   Main words in this unit: %s' % ', '.join(L.head for L in u.lessons))
                o.append('   New items registered in this unit: %d   |   Database total after this unit: %s'
                         % (len(uitems), thousands(u.lessons[-1].db_after) if u.lessons else '0'))
                o.append(wrap_list(sorted({it.lemma for it in uitems}, key=str.lower)))
                o.append('')
            if pi == len(parts):
                o.append(RULE)
                o.append('UPDATED VOCABULARY INDEX — END OF LEVEL %s' % lvl)
                o.append(RULE)
                o.append('   Main words covered at %s (%d):' % (lvl, len(lessons)))
                o.append(wrap_list(['%s (%s)' % (L.head, L.uid[-3:]) for L in lessons], '      '))
                o.append('')
                o.append('   All vocabulary introduced at %s, A–Z (%s items; the number is the lesson):'
                         % (lvl, thousands(len(items))))
                o.append(wrap_list(['%s %s' % (it.lemma, it.lesson[-3:])
                                    for it in sorted(items, key=lambda x: x.lemma.lower())], '      '))
                o.append('')
                o.append('   Cumulative database size after %s: %s individual vocabulary items '
                         '(+ %d structural words).' % (lvl, thousands(cum), len(db.structural)))
                o.append('   Global duplicate check for this level: PASSED (0 repeated items).')
                o.append('')
                o.append('END OF LEVEL %s' % lvl)
            files[name] = o
    return files, cum_by_level


def stats_table(db):
    rows = []
    tot = [0] * 7
    for lvl in LEVELS:
        ls = [L for u in db.units[lvl] for L in u.lessons]
        it = level_items(db, lvl)
        r = [len(ls), sum(1 for x in it if x.role == 'FAMILY'), sum(1 for x in it if x.role == 'COLLOCATE'),
             len(it), sum(len(L.exprs) for L in ls), sum(len(L.sents) for L in ls), len(db.units[lvl])]
        rows.append((lvl, r))
        tot = [a + b for a, b in zip(tot, r)]
    return rows, tot


def render_master(db, rel, files, qa):
    rows, tot = stats_table(db)
    refn = sum(1 for it in db.items if it.role == 'REFERENCE')
    o = [RULE, 'ENGLISH VOCABULARY MASTER SYSTEM — A1 TO C2   (English → Azerbaijani)',
         'MASTER INDEX AND GLOBAL DATABASE STATUS', RULE,
         'Generated: %s   |   Pronunciation: British English (IPA)   |   Spelling: British' % TODAY, '']
    o.append('1. WHAT THIS SYSTEM IS')
    o.append(THIN)
    o.append(wrap('A network-based vocabulary curriculum for an Azerbaijani-speaking learner. Words are never '
                  'taught alone: every MAIN WORD is the hub of a small network made of its word family, 7–8 '
                  'natural expressions, example sentences and a usage explanation. A global database guarantees '
                  'that no word is ever taught twice anywhere between A1 and C2.', '   '))
    o.append(wrap('This is a finite, growing database. It does not contain every English word, and CEFR levels '
                  'are not universally fixed lists. Each lesson was placed at a level by the author, according to '
                  'the difficulty of the expression network it teaches, and the placement was then cross-checked '
                  'against two open CEFR word lists (CEFR-J for A1–B2, Octanove for C1–C2). Where those lists give a '
                  'headword a different level, the lesson says so in a "Level note"; the full comparison is in '
                  'database/qa_report.txt.', '   '))
    o.append('')
    o.append('2. FILES')
    o.append(THIN)
    o.append('   ENGLISH_VOCABULARY_MASTER/')
    o.append('      MASTER_INDEX.txt ............ this file: rules, statistics, all six tracking records, roadmap')
    for name in files:
        lvl = name[:2]
        o.append('      %s %s level %s lessons' % (name, '.' * max(2, 28 - len(name)), lvl))
    o.append('      GLOBAL_LEARNED_WORDS.txt .... every vocabulary item A–Z with level, lesson and source expression')
    o.append('   database/vocabulary_db.json ..... the same database in machine-readable form (reusable across sessions)')
    o.append('   database/learned_words.tsv ...... one line per learned word (for quick searching)')
    o.append('   source/ ......................... hand-written lesson sources; tools/vocab.py rebuilds everything')
    o.append('')
    o.append('3. STATISTICS')
    o.append(THIN)
    o.append('   Level   Units  Main words  Family forms  New collocate words  Items total  Expressions  Sentences')
    for lvl, r in rows:
        o.append('   %-6s %6d %11d %13d %20d %12d %12d %10d' % (lvl, r[6], r[0], r[1], r[2], r[3], r[4], r[5]))
    o.append('   %-6s %6d %11d %13d %20d %12d %12d %10d' % ('TOTAL', tot[6], tot[0], tot[1], tot[2], tot[3], tot[4], tot[5]))
    o.append('')
    o.append('   Individual vocabulary items in the database: %s' % thousands(tot[3] + refn))
    o.append('      = %d main words + %d word-family forms + %s new words taught inside expressions + %d reference-set words'
             % (tot[0], tot[1], thousands(tot[2]), refn))
    o.append('   Structural (grammar) words taught once in A1 Section 0 and reusable as glue: %d' % len(db.structural))
    o.append('   Expressions and collocations: %s   |   Example sentences with translation: %s'
             % (thousands(tot[4]), thousands(tot[5])))
    o.append('')
    o.append('4. THE GLOBAL NO-REPETITION SYSTEM (exactly as enforced by the checker)')
    o.append(THIN)
    for t in [
        'R1. One database for all levels. It is never reset between A1 and C2.',
        'R2. Every main word, every word-family form and every content word inside an expression is registered '
        'the first time it is taught. Registering it a second time is an error and the build stops.',
        'R3. Inside an expression, each word must be (a) the main word of that lesson or one of its listed family '
        'forms, (b) a structural word from A1 Section 0, or (c) a brand-new word that has never been taught. '
        'A word that was taught in any other lesson may not appear in an expression.',
        'R4. Matching is done on dictionary forms, not on spelling: result/results, make/made/making, '
        'child/children, shop/shopping are the same item. Genuinely different words that merely look alike '
        '(e.g. new/news) must be declared one by one in source/distinct_lexemes.txt and are listed in Record 6.',
        'R5. Every expression is unique in the whole system.',
        'R6. A hyphenated compound (long-term, old-fashioned) is one dictionary item of its own.',
        'R7. Example sentences and usage explanations may recycle words that were already taught, and they are '
        'where very common collocations of two already-taught words are shown. They never introduce new '
        'teaching targets.',
        'R8. Main words planned for future parts (the roadmap in section 11) are reserved: they cannot be used up '
        'as collocates in other lessons before their own lesson is written.',
        'R9. Words from the same family that are taught in different lessons (each form still only once) are '
        'cross-referenced, so the network stays connected without repetition (Record 6b).',
    ]:
        o.append(wrap(t, '   ', '       '))
    o.append('')
    # Record 1
    o.append('5. RECORD 1 — MAIN WORDS COVERED (%d)' % tot[0])
    o.append(THIN)
    for lvl in LEVELS:
        for u in db.units[lvl]:
            o.append('   %s  UNIT %d — %s' % (lvl, u.no, u.en))
            for L in u.lessons:
                o.append(wrap('%s  %-16s %-18s /%s/  —  %s' % (L.uid, L.head, L.pos, L.ipa.split(',')[0].strip(), L.az),
                              '      ', ' ' * 14))
        o.append('')
    # Record 2
    allitems = sorted([it for it in db.items], key=lambda x: (x.lemma.lower(), x.seq))
    o.append('6. RECORD 2 — ALL INDIVIDUAL VOCABULARY ITEMS COVERED (%s)' % thousands(len(allitems)))
    o.append(THIN)
    o.append('   Format: word (lesson). M = main word, F = family form; no letter = taught inside an expression.')
    o.append('   Full details for each word are in GLOBAL_LEARNED_WORDS.txt.')
    letter = None
    buf = []

    def flush():
        if buf:
            o.append(wrap(', '.join(buf), '   %s  ' % letter, '      '))

    for it in allitems:
        l0 = it.lemma[0].upper()
        if l0 != letter:
            flush()
            buf = []
            letter = l0
        tag = {'MAIN': ' M', 'FAMILY': ' F', 'REFERENCE': ' ref'}.get(it.role, '')
        buf.append('%s (%s%s)' % (it.lemma, it.lesson, tag))
    flush()
    o.append('')
    # Record 3
    exprs = sorted(((en, L.uid, L.head) for L in db.lessons for (en, az, note, rl) in L.exprs),
                   key=lambda x: x[0].lower())
    o.append('7. RECORD 3 — ALL EXPRESSIONS AND COLLOCATIONS COVERED (%s)' % thousands(len(exprs)))
    o.append(THIN)
    col = []
    for en, uid, head in exprs:
        col.append('%s [%s]' % (en, uid))
    o.append(wrap('; '.join(col), '   ', '   '))
    o.append('')
    # Record 4
    o.append('8. RECORD 4 — WORD-FAMILY FORMS COVERED (%d)' % tot[1])
    o.append(THIN)
    for L in db.lessons:
        fam = ['%s (%s)' % (f, c) for c, _ in CATS for f, a in L.family[c]]
        if fam:
            o.append(wrap('%s %s: %s' % (L.uid, L.head, ', '.join(fam)), '   ', '          '))
    o.append('')
    # Record 5
    o.append('9. RECORD 5 — CEFR CLASSIFICATION')
    o.append(THIN)
    o.append(wrap('Every item carries the level of the lesson in which it is first taught. A lesson is placed at '
                  'the level of the expression network it teaches, so a very common headword (for example TRAVEL '
                  'or KEEP) can sit one level above its own wordlist level; whenever the open reference wordlist '
                  'gives the headword a different level, the lesson says so in a "Level note" line. The new words '
                  'inside the expressions are chosen at, or close to, the level of the lesson.', '   '))
    for lvl, r in rows:
        o.append('   %s %-20s %4d main words, %5d items' % (lvl, LEVEL_NAME[lvl], r[0], r[3]))
    if qa:
        o.append('')
        o.append('   Automatic cross-check against open reference lists (CEFR-J Wordlist 1.5, Octanove C1/C2 1.0):')
        for line in qa:
            if 'summary:' in line or re.match(r'\s+[ABC][12]: \d+ of', line):
                o.append('   ' + line.strip())
    o.append('')
    # Record 6
    o.append('10. RECORD 6 — DUPLICATE DETECTION STATUS')
    o.append(THIN)
    o.append('   Result of the last build: PASSED')
    o.append('   Items checked: %s   |   Expressions checked: %s   |   Repeated items: 0   |   Repeated expressions: 0'
             % (thousands(len(db.items)), thousands(tot[4])))
    o.append('')
    o.append('   6a. Look-alike pairs declared to be DIFFERENT words (%d):' % len(db.distinct_used))
    for pair in sorted(db.distinct_used, key=lambda p: sorted(p)):
        a, b = sorted(pair)
        o.append(wrap('%s / %s — %s' % (a, b, db.distinct.get(pair, '')), '       ', '          '))
    pairs = set()
    for a_seq, d in rel.items():
        for b_seq in d:
            pairs.add((min(a_seq, b_seq), max(a_seq, b_seq)))
    o.append('')
    o.append('   6b. Members of one word family taught in different lessons, each exactly once (%d links):' % len(pairs))
    lines = []
    for a_seq, b_seq in sorted(pairs, key=lambda p: db.items[p[0]].lemma.lower()):
        a, b = db.items[a_seq], db.items[b_seq]
        lines.append('%s [%s] ~ %s [%s]' % (a.lemma, a.lesson, b.lemma, b.lesson))
    o.append(wrap('; '.join(lines), '       ', '       ') if lines else '       —')
    o.append('')
    # Roadmap
    done = {L.head.lower() for L in db.lessons}
    o.append('11. ROADMAP — MAIN WORDS RESERVED FOR THE NEXT PARTS')
    o.append(THIN)
    any_left = False
    for lvl in LEVELS:
        left = [h for h, f in db.roadmap[lvl] if h.lower() not in done]
        if left:
            any_left = True
            o.append(wrap('%s (%d): %s' % (lvl, len(left), ', '.join(left)), '   ', '        '))
    if not any_left:
        o.append('   (no reserved main words at the moment)')
    o.append('')
    o.append('12. HOW TO CONTINUE IN A NEW SESSION')
    o.append(THIN)
    for t in ['1. Keep the whole repository (source/, tools/, database/, ENGLISH_VOCABULARY_MASTER/).',
              '2. Draft new lessons and test them first:  python3 tools/vocab.py check plan.txt',
              '3. Add the finished lessons to source/<LEVEL>/ (same line format as the existing files).',
              '4. Rebuild:  python3 tools/vocab.py build   — the build refuses to write files if any word or '
              'expression is repeated, so the database can never silently lose or duplicate a record.',
              '5. When a level grows beyond %d lessons the builder automatically splits it into numbered parts '
              '(A1_VOCABULARY_PART_02.txt ...) and lists them in this index.' % MAX_LESSONS_PER_FILE]:
        o.append(wrap(t, '   ', '      '))
    o.append('')
    o.append('END OF MASTER INDEX')
    return o


def render_global(db, rel):
    out_files = OrderedDict()
    head = [RULE, 'ENGLISH VOCABULARY MASTER SYSTEM — A1 TO C2   (English → Azerbaijani)',
            'GLOBAL LEARNED WORDS — the complete no-repetition database', RULE,
            'Generated: %s' % TODAY, '']
    o = list(head)
    o.append('PART A — STRUCTURAL WORDS (%d forms; taught once in A1 Section 0; reusable inside expressions)'
             % len(db.structural))
    o.append(THIN)
    for kind, en, az, rows in db.groups:
        if kind == 'STRUCTURAL':
            o.append(wrap('%s: %s' % (en, ', '.join(f for forms, a in rows for f in forms)), '   ', '      '))
    o.append('')
    refs = [it for it in db.items if it.role == 'REFERENCE']
    o.append('PART B — REFERENCE SETS (%d words; taught once in A1 Section 0)' % len(refs))
    o.append(THIN)
    for kind, en, az, rows in db.groups:
        if kind != 'STRUCTURAL':
            o.append(wrap('%s: %s' % (en, ', '.join('%s (%s)' % (f, a) for forms, a in rows for f in forms)),
                          '   ', '      '))
    o.append('')
    items = sorted([it for it in db.items if it.role != 'REFERENCE'], key=lambda x: (x.lemma.lower(), x.seq))
    o.append('PART C — ALL VOCABULARY ITEMS A–Z (%s)' % thousands(len(items)))
    o.append(THIN)
    o.append('   word | role | level | lesson (main word) | where and how it was taught')
    o.append('   Roles: MAIN = main word of a lesson, FAMILY = word-family form, NEW = new word inside an expression')
    o.append('')
    chunks, cur = [], []
    letter = None
    for it in items:
        l0 = it.lemma[0].upper()
        if l0 != letter:
            letter = l0
            cur.append('')
            cur.append('— %s —' % letter)
        if it.role == 'MAIN':
            how = 'main word — %s' % it.az
        elif it.role == 'FAMILY':
            how = 'word family (%s) — %s' % (it.cat, it.az)
        else:
            how = '"%s" — %s' % (it.expr, it.expr_az)
        see = sorted(rel.get(it.seq, {}).values(), key=lambda x: x.lemma.lower())
        if see:
            how += '   [see also: %s]' % ', '.join('%s %s' % (x.lemma, x.lesson) for x in see)
        role = 'NEW' if it.role == 'COLLOCATE' else it.role
        cur.append(wrap('%s | %s | %s | %s (%s) | %s' % (it.lemma, role, it.level, it.lesson, it.head, how),
                        '   ', '        '))
        if len(cur) > MAX_ITEMS_PER_GLOBAL_FILE:
            chunks.append(cur)
            cur = []
    chunks.append(cur)
    tail = ['', 'PART D — CHECK', THIN,
            '   Total individual vocabulary items: %s   |   Repeated items: 0   |   Duplicate check: PASSED'
            % thousands(len(db.items)), '', 'END OF GLOBAL LEARNED WORDS']
    for i, ch in enumerate(chunks, 1):
        name = 'GLOBAL_LEARNED_WORDS.txt' if i == 1 else 'GLOBAL_LEARNED_WORDS_PART_%02d.txt' % i
        body = (o if i == 1 else list(head) + ['(continued, part %d of %d)' % (i, len(chunks))]) + ch
        if i == len(chunks):
            body += tail
        else:
            body += ['', '(continues in GLOBAL_LEARNED_WORDS_PART_%02d.txt)' % (i + 1)]
        out_files[name] = body
    return out_files


def export_json(db, rel):
    lessons = []
    for L in db.lessons:
        lessons.append(OrderedDict([
            ('id', L.uid), ('level', L.level), ('unit', L.unit.en), ('main_word', L.head), ('pos', L.pos),
            ('ipa_british', L.ipa), ('azerbaijani', L.az), ('key_forms', L.forms),
            ('word_family', OrderedDict((c, [OrderedDict([('form', f), ('az', a)]) for f, a in L.family[c]])
                                        for c, _ in CATS)),
            ('expressions', [OrderedDict([('en', en), ('az', az), ('usage', note), ('related_only', rl)])
                             for en, az, note, rl in L.exprs]),
            ('sentences', [OrderedDict([('en', en), ('az', az)]) for en, az in L.sents]),
            ('usage', L.usage),
            ('new_items', [it.lemma for it in L.new_items]),
        ]))
    return OrderedDict([
        ('generated', TODAY),
        ('levels', LEVELS),
        ('structural_words', sorted(db.structural)),
        ('items', [it.as_dict() for it in db.items]),
        ('lessons', lessons),
        ('reserved_main_words', OrderedDict((l, [h for h, f in db.roadmap[l]
                                                 if h.lower() not in db.lesson_by_head]) for l in LEVELS)),
    ])


def report(db, limit=60):
    for e in db.errors[:limit]:
        print('ERROR  ' + e)
    if len(db.errors) > limit:
        print('... %d more errors' % (len(db.errors) - limit))
    for w in db.warnings[:limit]:
        print('warn   ' + w)


def sync_ref_levels(db, refs):
    """Reference-list level of every main word.  Cached in source/reference_levels.tsv so that the
    generated files stay identical when the external reference data is not available."""
    path = os.path.join(SRC, 'reference_levels.tsv')
    cache = OrderedDict()
    if os.path.exists(path):
        for raw in open(path, encoding='utf-8'):
            if raw.startswith('#') or not raw.strip():
                continue
            w, _, lv = raw.rstrip('\n').partition('\t')
            cache[w] = lv
    if refs.get('cefr'):
        for L in db.lessons:
            lv = refs['cefr'].get(L.head.lower())
            cache[L.head.lower()] = LEVELS[lv] if lv is not None else '-'
        with open(path, 'w', encoding='utf-8') as f:
            f.write('# main word <TAB> level in the open reference lists (CEFR-J Wordlist 1.5 for A1-B2, '
                    'Octanove C1/C2 1.0); "-" = not listed.  Written by tools/vocab.py build.\n')
            for w in sorted(cache):
                f.write('%s\t%s\n' % (w, cache[w]))
    return cache


def cmd_build(args):
    db = build_db()
    report(db)
    rows, tot = stats_table(db)
    print(' | '.join('%s:%d' % (lvl, r[0]) for lvl, r in rows),
          '| lessons=%d items=%d expressions=%d errors=%d warnings=%d'
          % (tot[0], len(db.items), tot[4], len(db.errors), len(db.warnings)))
    if db.errors:
        print('BUILD STOPPED: fix the errors above; no output files were written.')
        return 1
    rel = cross_refs(db)
    refs = load_refs()
    db.ref_levels = sync_ref_levels(db, refs)
    qa = qa_report(db, refs) if (refs['cefr'] or refs['ipa']) else []
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(DBD, exist_ok=True)
    files, _ = render_level_files(db, rel)
    allfiles = OrderedDict()
    allfiles['MASTER_INDEX.txt'] = render_master(db, rel, files, qa)
    allfiles.update(files)
    allfiles.update(render_global(db, rel))
    for old in os.listdir(OUT):
        if old.endswith('.txt') and old not in allfiles:
            os.remove(os.path.join(OUT, old))
    for name, lines in allfiles.items():
        with open(os.path.join(OUT, name), 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines).rstrip('\n') + '\n')
    with open(os.path.join(DBD, 'vocabulary_db.json'), 'w', encoding='utf-8') as f:
        json.dump(export_json(db, rel), f, ensure_ascii=False, indent=1)
    with open(os.path.join(DBD, 'learned_words.tsv'), 'w', encoding='utf-8') as f:
        f.write('word\trole\tlevel\tlesson\tmain_word\texpression\ttranslation\n')
        for it in sorted(db.items, key=lambda x: x.lemma.lower()):
            f.write('\t'.join([it.lemma, it.role, it.level, it.lesson, it.head, it.expr or '',
                               it.expr_az or it.az or '']) + '\n')
    if qa:
        with open(os.path.join(DBD, 'qa_report.txt'), 'w', encoding='utf-8') as f:
            f.write('\n'.join(qa) + '\n')
    print('BUILD OK: wrote %d TXT files to %s' % (len(allfiles), os.path.relpath(OUT, ROOT)))
    return 0


def cmd_check(args):
    text = sys.stdin.read() if (not args or args[0] == '-') else open(args[0], encoding='utf-8').read()
    db = build_db()
    base_err = len(db.errors)
    if base_err:
        print('(database already has %d errors - run build)' % base_err)
    refs = load_refs()
    cefr = refs['cefr']
    total_new = 0
    for n, raw in enumerate(text.splitlines(), 1):
        s = raw.strip()
        if not s or s.startswith('//'):
            continue
        m = re.match(r'^(A1|A2|B1|B2|C1|C2)\s+(.*?)\s*::\s*(.*)$', s)
        if not m:
            print('plan line %d not understood: %s' % (n, s[:50]))
            continue
        lvl, left, right = m.groups()
        head, _, fam = left.partition('+')
        L = Lesson(lvl, None, head.strip(), 'adjective verb', '', '', 'plan', n)
        L.plan = True
        L.uid = '%s-new' % lvl
        for x in fam.split(','):
            if x.strip():
                L.family['n'].append((x.strip(), '?'))
        for e in right.split('|'):
            e = e.strip()
            if e:
                L.exprs.append((e.lstrip('~ ').strip(), '?', '?', e.startswith('~')))
        before = len(db.errors)
        process_lesson(db, L)
        msgs = [x.split(': ', 1)[1] for x in db.errors[before:]]
        new = [it for it in L.new_items if it.role == 'COLLOCATE']
        total_new += len(new)
        flags = []
        li = LEVELS.index(lvl)
        if cefr:
            r = cefr.get(L.head.lower())
            if r is not None and r != li:
                flags.append('MAIN=%s' % LEVELS[r])
            for it in new:
                r = cefr.get(it.lemma.lower())
                if r is not None and r - li >= 2:
                    flags.append('%s=%s' % (it.lemma, LEVELS[r]))
        if len(L.exprs) != 8:
            msgs.append('has %d expressions' % len(L.exprs))
        if msgs or flags:
            print('%s %s  new=%d %s' % (lvl, L.head, len(new), ('levels: ' + ' '.join(flags)) if flags else ''))
            for x in msgs:
                print('    ' + x)
    print('plan checked: %d new collocate words; %d problems' % (total_new, len(db.errors) - base_err))
    return 0


def cmd_find(args, only_free=False):
    db = build_db()
    for w in args:
        low = w.lower()
        hits = OrderedDict()
        if low in db.structural:
            print('%s: STRUCTURAL' % w)
            continue
        for c in candidates(low):
            it = db.by_form.get(c)
            if it is not None:
                hits[id(it)] = it
        for it in db.by_cand.get(low, ()):
            hits[id(it)] = it
        r = None
        for c in candidates(low):
            r = r or db.reserved.get(c)
        if hits:
            if not only_free:
                for it in hits.values():
                    print('%s: %s %s %s %s' % (w, it.role, it.lesson, it.head, '"%s"' % it.expr if it.expr else ''))
        elif r and r[0].lower() not in db.lesson_by_head:
            print('%s: RESERVED for %s (%s)' % (w, r[0], r[1]))
        elif only_free:
            print('%s: free' % w)
        else:
            print('%s: not in database' % w)
    return 0


def main(argv):
    if len(argv) < 2 or argv[1] not in ('build', 'check', 'find', 'free'):
        print(__doc__)
        return 2
    if argv[1] == 'build':
        return cmd_build(argv[2:])
    if argv[1] == 'check':
        return cmd_check(argv[2:])
    return cmd_find(argv[2:], only_free=(argv[1] == 'free'))


if __name__ == '__main__':
    sys.exit(main(sys.argv))
