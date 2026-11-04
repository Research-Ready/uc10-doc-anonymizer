"""UC10 Document Anonymizer — Static Wordlists, Regex Patterns, and Configurations.

Central repository for languages, entities, regex patterns, acronyms, brand lists,
and dictionary frequency thresholds.
"""

from __future__ import annotations

import re
try:
    from presidio_analyzer import Pattern
except ImportError:
    from dataclasses import dataclass

    @dataclass
    class Pattern:
        name: str
        regex: str
        score: float

SUPPORTED_LANGUAGES: list[str] = ["nl", "en"]

# Dutch label prefix per Presidio entity type
_LABEL_PREFIX: dict[str, str] = {
    "PERSON": "PERSOON",
    "ORGANIZATION": "ORGANISATIE",
    "DATE_TIME": "DATUM",
    "PHONE_NUMBER": "TELEFOON",
    "EMAIL_ADDRESS": "EMAIL",
    "LOCATION": "LOCATIE",
    "URL": "URL",
    "IBAN_CODE": "IBAN",
    "CREDIT_CARD": "CREDITCARD",
    "IP_ADDRESS": "IP_ADRES",
    "ID_NUMBER": "ID",
}

# Entities detected for anonymization: people and direct identifiers
DETECTED_ENTITIES: list[str] = [
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "ID_NUMBER",
    "IBAN_CODE",
    "CREDIT_CARD",
    "IP_ADDRESS",
]

# Organisations and places detected to resolve overlapping NER false positives
_ANALYZE_ENTITIES: list[str] = DETECTED_ENTITIES + ["ORGANIZATION", "LOCATION"]

# Prefix for target company replacements
_TARGET_PREFIX: str = "ORGANISATIE_"

# Regex patterns for organizations NER commonly misses or truncates
_ORG_PATTERNS = [
    # Name + legal form: "ValueChain Hackers BV", "Acme Ltd"
    Pattern(
        "org_legal_form",
        r"\b(?:[A-Z][\w&'-]*[ \t]+){1,4}(?:B\.V\.|N\.V\.|V\.O\.F\.|BV|NV|VOF|Ltd\.?|Inc\.?|GmbH|LLC)(?!\w)",
        0.85,
    ),
    # Institution word + name: "Gemeente Utrecht", "Ministerie van Binnenlandse Zaken"
    Pattern(
        "org_institution",
        r"\b(?:Stichting|Vereniging|Gemeente|Provincie|Rijksuniversiteit|Universiteit|Hogeschool"
        r"|Ministerie|Waterschap|Coöperatie)(?:[ \t]+(?:van|voor|der|de)?[ \t]*[A-Z][\w'-]+){1,4}",
        0.85,
    ),
]

# Student and employee numbers ("S1234567")
_ID_PATTERNS = [Pattern("student_number", r"\b[sSpPuU]\d{6,8}\b", 0.7)]

# Written-out dates, Dutch and English months
_MONTH_FULL = (
    r"(?:january|february|march|april|may|june|july|august|september|october|november|december"
    r"|januari|februari|maart|april|mei|juni|juli|augustus|oktober)"
)
_MONTH = rf"(?:{_MONTH_FULL}|(?:jan|feb|mar|mrt|apr|jun|jul|aug|sept?|oct|okt|nov|dec)\.?)"

_DATE_PATTERNS = [
    Pattern("date_d_month_y", rf"\b\d{{1,2}}(?:st|nd|rd|th|e)?\s+{_MONTH},?\s+(?:19|20)\d{{2}}\b", 0.85),
    Pattern("date_month_d_y", rf"\b{_MONTH}\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+(?:19|20)\d{{2}}\b", 0.85),
    Pattern("date_d_month", rf"\b\d{{1,2}}(?:st|nd|rd|th|e)?\s+{_MONTH_FULL}\b", 0.7),
    Pattern("date_month_y", rf"\b{_MONTH_FULL}\s+(?:19|20)\d{{2}}\b", 0.7),
]

# Title + surname ("mevrouw De Groot", "dr. Janssen")
_TITLED_NAME = re.compile(
    r"(?i:\b(?:mevrouw|mevr\.|mw\.|meneer|mijnheer|dhr\.|de heer|dr\.|prof\.|drs\.|ir\.|mr\.|mrs\.|ms\.))"
    r"[ \t]+(?P<name>(?:[A-Z]\.[ \t]?)*(?:(?:[Vv]an|[Dd]e|[Dd]er|[Dd]en|[Tt]er|[Tt]en|[Hh]et)[ \t]+)*"
    r"[A-Z][\w'-]+(?:[ \t]+[A-Z][\w'-]+)?)"
)

_PHONE_REGIONS: tuple[str, ...] = ("NL", "BE", "DE", "UK", "US", "FR")
_PHONE_CONTEXT: list[str] = [
    "telefoon", "telefonisch", "tel", "telnr", "mobiel", "bel", "bellen", "bereikbaar",
    "nummer", "phone", "telephone", "mobile", "call", "number",
]

# Function words for per-line language detection
_NL_WORDS: set[str] = {
    "de", "het", "een", "en", "van", "op", "met", "niet", "zijn", "dat", "voor", "er", "te",
    "u", "ik", "je", "wij", "zij", "hij", "ook", "aan", "om", "bij", "als", "naar", "maar",
    "dan", "nog", "wel", "mijn", "hoe", "sinds", "kunt", "wordt", "werd", "heeft", "hebben",
    "deze", "dit", "wat", "waar", "geen", "meer", "over", "uit", "tot", "door", "staat",
}

_EN_WORDS: set[str] = {
    "the", "a", "and", "on", "with", "not", "are", "that", "for", "to", "you", "we", "he",
    "she", "it", "from", "at", "by", "as", "but", "this", "be", "was", "her", "his", "has",
    "have", "which", "what", "where", "no", "more", "about", "out", "until", "through",
    "will", "would", "can", "our", "their", "they", "planned", "call", "been",
}

_TABLE_RULE: re.Pattern = re.compile(r"^\|?[\s:|-]+\|?$")
_ANALYZE_CHUNK: int = 50_000
_ORG_TAIL: re.Pattern = re.compile(r"\s+(?:van|de|of|from|bij|at)\s+[A-Z]{2,}\.?$")
_NAME_TAIL: re.Pattern = re.compile(r"(?:[ \t]+[A-Z][\w'-]*[\w])+")
_MONTHS: tuple[str, ...] = (
    "jan", "feb", "mar", "maa", "apr", "may", "mei", "jun", "jul", "aug", "sep", "oct", "okt", "nov", "dec",
)
_DATE_SHAPE: re.Pattern = re.compile(r"\b(?:19|20)\d{2}\b|\b\d{1,2}[-/.]\d{1,2}(?:[-/.]\d{2,4})?\b")

_CONNECTORS: set[str] = {
    "of", "for", "and", "the", "to", "in", "on", "a", "an", "with", "van", "de", "der", "den",
    "het", "een", "voor", "en", "met", "op",
}
_CODE: re.Pattern = re.compile(r"^[A-Z]{1,2}\d{1,3}$")
_TECH_TERM: re.Pattern = re.compile(r"^[a-z][A-Z]{2,5}s?$")
_COMMON_FREQ: int = 100
_COMMON_WORDS: set[str] = set()
_COMMON_EN: set[str] = set()
_ALL_EN: set[str] = set()

_GENERIC_ACRONYMS: set[str] = set(
    """erp plm pdm mrp mes crm cad cam cae bom ebom mbom bop eto mto ato mts wms scm api
    saas it ict bi kpi ai iot hr msc bsc mba phd ceo cfo cto coo sme mkb""".split()
)

# 1,059 common words that are also first names or surnames
_NAME_WORDS: set[str] = set(
    """
    abbott ada adam adrian agatha ahmed al alan albert alberto alejandro alex alexander alexis alfred alice
    alison allan allen alvin amanda ami amigo amir amos amy anderson andre andrea andrew andy angela angelica
    angus anita ann anna anne annie anthony anton antonio antony april archie ariel armstrong arne arnold art
    arthur aubrey audrey augustus autumn avery baas baker bakker banks barbara barber barney baron barrett
    barrio barry bart barton bas becky beek belinda bell ben benjamin benny berg bernard bernie bert beth
    bethany betsy betty beverly bill billie billy bird bishop black blaine blair blake bob bobby boer bond
    bonnie boom boon boris bos boyd brad bradford bradley brandi brandon brandy brenda brendan brent bret
    brett brewer brian bridget briggs brink broek brooke brown bruce bruin bruno bryan bryce buck bud bush
    butler byron caesar caleb calvin capability carl carlo carlos carol carole caroline carolyn carpenter
    carter cary case casey casper cassandra catherine cathy cecilia celeste celia charity charlene charles
    charley charlie chastity cherie chip chris christian christie christina christophe christopher chuck
    cinderella cindy claire clara clare clarence clarissa clark claude claudia claudio clay clayton cliff
    clifford clive clyde cody cole colin conan connie conrad cook cooper corey cory courtney craig crane
    cristina curt curtis cynthia cyrus dale dalton dam damon dan dana daniel danielle danny darren darryl
    daryl dave david davis dawn dawson day deadly dean deb debbie deborah del denis denise dennis derek devon
    dewey diana diane dick dijk dion dirk dominic don donald donna donnie donovan dora dorian dorothy dory
    doug douglas doyle draper drew duane duke duncan dustin dwayne dwight dylan earl ed eddie eddy edgar edith
    edmond edmund eduardo edward edwin eileen elaine eli elias elijah eliot elisabeth elizabeth ellen elliot
    elliott elsa elvis emil emily emma emmett eric erica erik ernest ernie ernst esther ethan ethel eugene eva
    evan eve evelyn everett faith fay felix finn fisher fletcher fleur floor floyd fox frances francis
    francisco francois frank franklin fred frederick fritz frost fuzzy gabriel gail gale gardener gary gates
    gay gene geoffrey george gerald gerard gertrude gideon gil giles gill ginny giovanni glen glenn gold
    gordon graaf grace graham grant green greg gregory gretchen groen groot guillermo gunnar guy gypsy haan
    hal hall hamilton hamlet hank hans harm harmon harold harper harriet harris harrison harry hart harvey
    hayes hazel heather hector heidi helen henry herb herbert herman heuvel hilary hilda hill hillary hoek
    holly holmes hon hope horatio howard huey hugh hughes hunt hunter hyacinth ian igor indiana inge ingrid
    ira iris irving isaac isabelle isis israel jack jacob jacobs jacques jade jaime james jamie jan jane janet
    janice jared jarl jarvis jason jay jean jeanne jeannie jeff jeffrey jen jennifer jenny jeremy jerome jerry
    jess jesse jessica jesus jet jill jim jimmy joan joanne job jock joe joel johann john johnnie johnny jon
    jonathan jones jong jordan jorge jose joseph josh joshua joy joyce juan judge judith judy julia julian
    julie juliet julius jun june justin karen kari karin karl kate kathleen kathryn kathy katrina kay kees
    keith keizer kelly kelvin ken kenneth kent kerry kevin kim kimberly king kirk kirsten kit kitty klaus
    knapper knight kok koning koopman kramer kris kristen kristin kroon kurt kyle lana lance lancelot lane
    lange lara larry lars laura laurel lauren laurence laurent laurie lawrence layla lea leads leah lee
    leeuwen leigh leila len lenny leo leon leonard les leslie lester lewis lex liam lila lin linda linden
    lindsay lindsey lisa list little liz liza lloyd lois lola long loon lord lorenzo lori lorraine lou louie
    louis louise love lucifer lucius lucy lui luis luke lynn maas mac madonna major malcolm mandy mann manuel
    mara marc marcel marcia marco margaret margot maria marian marie marilyn mario marion mark marsh marshall
    martha martin marty marvin mary mason mat mats matt matthew maureen maurice max may mayo meer meg megan
    melinda meyer micah michael michel michelle mick mickey micky mike miles miller mills milo miriam mitch
    mitchell moe mohammad mol molenaar molly mongo monica monique montgomery monty moore moran morgan morris
    moses mulder murray nancy naomi natalie nate nathan nathaniel neal ned neil newman nicholas nick nicola
    nicolas nigel nikolai nils nina ninja no noah noble noel nora norm norma norman norris north nou old olive
    oliver olivier omar oscar oswald owen oz pablo page palmer pam pamela panacea panzer parker part pascal
    pat patrice patricia patrick patty paul paula pauline pearl pedro peggy penny per percival percy peregrine
    perry pete peter peters petra phil philip philippe phillip pierce pierre piet pilot ping plastic po polly
    pool pope porter post potter pratt price prins purity quentin rachael rachel rafael rain raj raja ralph
    ram ramon ramsey rand randall randolph randy raphael raquel raul ray raymond real rebecca reed rees reeve
    reg reginald reid rene reuben revised rex rhonda ricardo rice rich richard rick ricky rider rob robbie
    robert roberta roberto robin robyn rod rodent rodney roger rogue roland rolf roman ron ronald roos root
    rose ross roxanne roxie roy ruben rudolph rudy ruiter rupert rush russ russell rusty ruth sabrina sal
    sally sam samantha samuel sander sandra sandy sanity santa sara sarah sasha saul savannah sawyer schaap
    schipper scooter scot scott sean serena sergeant sergei sergio seth seymour shadow shane shankar shannon
    sharon sharp shatter shaw shawn sheila shepherd sherman shirley short sid sidney silver simon simone sir
    skeeter skip slater smid smith snow sofia son sonja sonny sophie sorrel south space spencer spike spock
    spy sri stacey stacy stagger stam stan stanley steel steen stefan stella stephanie stephen steve steven
    stewart stone storm strong stu stuart sue summer susan suzanne sven swan sweet tad tai tal tamara tammy
    tanner tanya tao tara taurus taylor ted teddy teresa teri terrance terrence terri terry tessa tex thad the
    theodore think thomas those ti tiberius tiger tim timothy tip tobias toby todd tolerant tom tomas tommy
    ton tony tor tracey tracy travis trent trevor trey tricia troy trying tucker tuna turner tyler una ursula
    val valentin valerie vance vaughn vern vernon veronica vic vice vicki vicky victor victoria vince vincent
    visser vivian vladimir vos vries wade walker waller wally walt walter ward warren wayne weaver webb wells
    wendell wendy werner wesley west wheeler white whitney wijk will william willie willy wilma wilson win
    winnie winston winter winters wit wolf wood woods woody wright xavier young yvette yvonne zoe zon zwart
""".split()
)

_BRAND_WORDS: set[str] = set(
    """shell apple amazon orange oracle target visa jumbo action gamma praxis hema blokker zeeman
    sligro total delta united subway sprint puma jaguar corona coach gap next boots mercury tesla ing
""".split()
)

_WORD: re.Pattern = re.compile(r"[^\W\d_]+")
_PARTICLES: set[str] = {
    "van", "de", "der", "den", "ter", "ten", "het", "von", "da", "di", "le", "la", "du", "del",
}
_NAME_TOKEN: re.Pattern = re.compile(
    r"^(?:[A-Z][\w'’-]+|(?:[A-Z]\.)+|(?:Prof|Dr|Drs|Ir|Mr|Mrs|Ms|Dhr|Mevr|Mw)\.?)$"
)

# OpenXML schemas & document markers
_W: str = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_MD_ESCAPE: re.Pattern = re.compile(r"\\([\\`*_{}\[\]()#+\-.!|<>~])")
_PERSON_ATTRS: set[str] = {"author", "initials", "userId"}

# Citations and reference section protection
_REF_HEADING: re.Pattern = re.compile(
    r"^[#\s]*(?:\d+(?:\.\d+)*\.?\s*)?(?:references|reference list|bibliography|works cited|"
    r"literature list|literatuurlijst|referenties|bronnen|bronvermelding|bibliografie)\s*:?\s*$",
    re.IGNORECASE,
)
_SECTION_END: re.Pattern = re.compile(
    r"^\s*(?:#{1,6}\s|(?:\d+(?:\.\d+)*\.?\s*)?(?:appendix|appendices|bijlage|bijlagen|annex)\b)",
    re.IGNORECASE,
)
_YEAR: str = r"(?:(?:1[89]|20)\d{2}[a-z]?|n\.d\.|in press)"
_PAGES: str = r"(?:,\s*(?:p|pp)\.\s*\d+(?:\s*[–-]\s*\d+)?)?"
_CITE_PART: re.Pattern = re.compile(
    rf"^\s*(?:(?:see|e\.g\.|cf\.|zie|bijv\.|i\.e\.)[,:]?\s+)?[A-Z][^;()]*?,?\s+{_YEAR}"
    rf"(?:\s*,\s*{_YEAR})*{_PAGES}\s*$"
)
_PAREN: re.Pattern = re.compile(r"\(([^()]{1,400})\)")
_NARRATIVE: re.Pattern = re.compile(
    rf"(?:(?:[A-Z][\w'’-]+|van|de|der|den|von|da|di)\s+){{0,3}}[A-Z][\w'’-]+"
    rf"(?:\s+et\s+al\.?|\s+(?:and|&|en)\s+(?:[A-Z][\w'’-]+\s+){{0,2}}[A-Z][\w'’-]+)?"
    rf"\s+\({_YEAR}(?:\s*[,;]\s*{_YEAR})*{_PAGES}\)"
)

_LABEL_CHARS: str = "ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789"
