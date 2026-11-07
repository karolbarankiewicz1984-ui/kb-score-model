"""Explicit club-name equivalences, scoped to one reviewed competition.

Targets are normalized football-data.co.uk spellings.  Matching always checks
all literal candidate names, so an alias can never choose between two targets.
No prefixes, suffix removal, edit distance or cross-league fallback is used.
"""
ALIASES_EXTRA = {
    "premier league": {
        "brighton and hove albion": "brighton",
        "coventry city": "coventry", "hull city": "hull", "luton town": "luton",
        "wolverhampton": "wolves",
    },
    "bundesliga": {
        "bayern munchen": "bayern munich", "fc bayern munchen": "bayern munich",
        "vfb stuttgart": "stuttgart", "borussia monchengladbach": "m gladbach",
        "eintracht frankfurt": "ein frankfurt", "mainz 05": "mainz",
        "1 fsv mainz 05": "mainz", "1 fc koln": "fc koln",
        "hamburger sv": "hamburg", "fc st pauli": "st pauli",
        "1 fc heidenheim": "heidenheim", "sv darmstadt 98": "darmstadt",
        "sc paderborn 07": "paderborn", "1 fc union berlin": "union berlin",
        "sc freiburg": "freiburg", "fc augsburg": "augsburg",
        "tsg hoffenheim": "hoffenheim", "vfl wolfsburg": "wolfsburg",
        "sv werder bremen": "werder bremen", "sv elversberg": "elversberg",
    },
    "serie a": {
        "ac monza": "monza", "hellas verona": "verona", "fc internazionale": "inter",
    },
    "la liga": {
        "atletico madrid": "ath madrid", "deportivo alaves": "alaves",
        "real betis": "betis", "celta vigo": "celta", "real sociedad": "sociedad",
        "espanyol": "espanol", "rayo vallecano": "vallecano",
        "deportivo a coruna": "la coruna", "racing santander": "santander",
        "real valladolid": "valladolid", "real oviedo": "oviedo",
        "cd leganes": "leganes", "ud las palmas": "las palmas",
    },
    "ligue 1": {
        "paris saint germain": "paris sg", "olympique lyonnais": "lyon",
        "olympique marseille": "marseille", "olympique de marseille": "marseille",
        "saint etienne": "st etienne", "as saint etienne": "st etienne",
        "clermont foot": "clermont",
    },
    "eredivisie": {
        "sc heerenveen": "heerenveen", "fortuna sittard": "for sittard",
        "fc groningen": "groningen", "fc twente": "twente", "fc utrecht": "utrecht",
        "nec nijmegen": "nijmegen", "pec zwolle": "zwolle", "ado den haag": "den haag",
        "almere city fc": "almere city", "rkc waalwijk": "waalwijk", "fc volendam": "volendam",
    },
    "primeira liga": {
        "sporting cp": "sp lisbon", "sporting lisbon": "sp lisbon", "braga": "sp braga",
        "sporting braga": "sp braga", "fc porto": "porto", "casa pia ac": "casa pia",
        "estrela da amadora": "estrela", "vitoria de guimaraes": "guimaraes",
    },
    "jupiler pro league": {
        "kv mechelen": "mechelen", "standard liege": "standard", "sk beveren": "beveren",
        "zulte waregem": "waregem", "royal antwerp": "antwerp", "kaa gent": "gent",
        "krc genk": "genk", "oh leuven": "oud heverlee leuven",
        "union saint gilloise": "st gilloise", "sint truiden": "st truiden",
    },
    "super lig": {
        "amed sportif": "amedspor", "corum fk": "corum", "erzurumspor fk": "erzurumspor",
        "basaksehir": "buyuksehyr", "istanbul basaksehir": "buyuksehyr",
        "gaziantep fk": "gaziantep", "goztepe": "goztep",
    },
    "premiership": {
        "dundee fc": "dundee", "heart of midlothian": "hearts",
        "st johnstone": "st johnstone", "st mirren": "st mirren",
    },
}

# The same explicitly identified English clubs can move between divisions.
# These spellings are reviewed against E1/E2/E3/EC CSVs, never borrowed from
# another league's candidate set during resolution.
ENGLISH_DIVISION_ALIASES = {
    "bolton wanderers": "bolton", "derby county": "derby", "wolverhampton wanderers": "wolves",
    "west ham united": "west ham", "leicester city": "leicester", "ipswich town": "ipswich",
    "leeds united": "leeds", "hull city": "hull", "coventry city": "coventry",
    "norwich city": "norwich", "luton town": "luton", "birmingham city": "birmingham",
    "blackburn rovers": "blackburn", "cardiff city": "cardiff", "charlton athletic": "charlton",
    "huddersfield town": "huddersfield", "lincoln city": "lincoln", "oxford united": "oxford",
    "plymouth argyle": "plymouth", "preston north end": "preston", "queens park rangers": "qpr",
    "rotherham united": "rotherham", "sheffield wednesday": "sheffield weds", "stoke city": "stoke",
    "swansea city": "swansea", "west bromwich albion": "west brom", "cambridge united": "cambridge",
    "wycombe wanderers": "wycombe", "peterborough united": "peterboro", "mansfield town": "mansfield",
    "burton albion": "burton", "bradford city": "bradford", "doncaster rovers": "doncaster",
    "stockport county": "stockport", "wigan athletic": "wigan", "bristol rovers": "bristol rvs",
    "carlisle united": "carlisle", "cheltenham town": "cheltenham", "exeter city": "exeter",
    "northampton town": "northampton", "shrewsbury town": "shrewsbury", "crewe alexandra": "crewe",
    "tranmere rovers": "tranmere", "grimsby town": "grimsby", "colchester united": "colchester",
    "swindon town": "swindon", "york city": "york", "accrington stanley": "accrington",
    "salford city": "salford", "oldham athletic": "oldham", "forest green rovers": "forest green",
    "harrogate town": "harrogate", "sutton united": "sutton",
}
for _league in ("championship", "league one", "league two", "national league"):
    ALIASES_EXTRA[_league] = dict(ENGLISH_DIVISION_ALIASES)

ALIASES_EXTRA["2 bundesliga"] = dict(ALIASES_EXTRA["bundesliga"], **{
    "1 fc nurnberg": "nurnberg", "energie cottbus": "cottbus", "dynamo dresden": "dresden",
    "arminia bielefeld": "bielefeld", "eintracht braunschweig": "braunschweig",
    "vfl osnabruck": "osnabruck", "hertha bsc": "hertha", "hannover 96": "hannover",
    "karlsruher sc": "karlsruhe", "sv wehen wiesbaden": "wehen", "ssv jahn regensburg": "regensburg",
})
ALIASES_EXTRA["serie b"] = dict(ALIASES_EXTRA["serie a"], **{"lr vicenza": "vicenza"})
ALIASES_EXTRA["la liga 2"] = dict(ALIASES_EXTRA["la liga"], **{
    "fc andorra": "andorra", "burgos cf": "burgos", "celta fortuna": "celta b",
    "real sociedad b": "sociedad b", "sporting gijon": "sp gijon", "racing ferrol": "ferrol",
    "real zaragoza": "zaragoza", "cd castellon": "castellon",
})
ALIASES_EXTRA["ligue 2"] = dict(ALIASES_EXTRA["ligue 1"], **{"annecy fc": "annecy", "pau": "pau fc"})

# Additional first divisions, verified against their separate /new/ CSV tables
# and matching PitchAPI league metadata in Actions run 42189744814. Generic
# league names are disambiguated before any of these aliases are considered.
ALIASES_EXTRA.update({
    "austrian bundesliga": {
        "austria lustenau": "a lustenau", "austria wien": "austria vienna",
        "rapid wien": "sk rapid", "wsg tirol": "tirol",
    },
    "brazilian serie a": {
        "athletico paranaense": "athletico pr", "botafogo": "botafogo rj",
        "chapecoense": "chapecoense sc", "flamengo": "flamengo rj",
        "rb bragantino": "bragantino", "vasco da gama": "vasco",
    },
    "russian premier league": {
        "dinamo moscow": "dynamo moscow", "fc krasnodar": "krasnodar",
        "fc orenburg": "orenburg", "fc rostov": "fk rostov", "fk akhmat": "akhmat grozny",
        "fakel": "fakel voronezh", "krylya sovetov samara": "krylya sovetov",
        "rodina": "rodina moscow", "zenit st petersburg": "zenit",
    },
    "danish superliga": {
        "ac horsens": "horsens", "brondby if": "brondby", "fc kobenhavn": "fc copenhagen",
        "fc midtjylland": "midtjylland", "ob": "odense", "agf": "aarhus",
        "fc nordsjaelland": "nordsjaelland",
    },
    "romanian superliga": {
        "arges": "fc arges", "botosani": "fc botosani", "corvinul hunedoara": "corvinul",
        "csikszereda": "csikszereda m ciuc", "otelul galati": "otelul", "petrolul 52": "petrolul",
        "rapid bucuresti": "fc rapid bucuresti", "sepsi": "sepsi sf gheorghe",
        "universitatea cluj": "u cluj", "universitatea craiova": "univ craiova", "voluntari": "fc voluntari",
    },
    "ekstraklasa": {
        "jagiellonia bialystok": "jagiellonia", "legia warszawa": "legia",
        "rakow czestochowa": "rakow", "wisla krakow": "wisla", "zaglebie lubin": "zaglebie",
    },
    "allsvenskan": {
        "halmstads bk": "halmstad", "ifk goteborg": "goteborg", "kalmar ff": "kalmar",
    },
    "j1 league": {
        "fagiano okayama fc": "okayama", "jef united chiba": "chiba", "kyoto sanga fc": "kyoto",
        "machida zelvia": "machida", "mito hollyhock": "mito", "tokyo verdy": "verdy",
        "urawa red diamonds": "urawa reds",
    },
    "liga mx": {
        "atletico de san luis": "atl san luis", "cf america": "club america",
        "chivas": "guadalajara chivas", "fc juarez": "juarez", "leon": "club leon",
        "pumas": "unam pumas", "queretaro fc": "queretaro", "tigres": "tigres uanl", "tijuana": "club tijuana",
    },
    "mls": {
        "atlanta united": "atlanta utd", "charlotte fc": "charlotte", "chicago fire fc": "chicago fire",
        "houston dynamo fc": "houston dynamo", "inter miami cf": "inter miami",
        "la galaxy": "los angeles galaxy", "new york city fc": "new york city",
        "red bull new york": "new york red bulls", "seattle sounders fc": "seattle sounders",
    },
    "liga profesional": {
        "argentinos juniors": "argentinos jrs", "atletico tucuman": "atl tucuman",
        "central cordoba de santiago": "central cordoba", "club atletico platense": "platense",
        "deportivo riestra": "dep riestra", "estudiantes": "estudiantes l p",
        "estudiantes de rio cuarto": "estudiantes rio cuarto", "gimnasia lp": "gimnasia l p",
        "independiente rivadavia": "ind rivadavia", "newell s old boys": "newells old boys",
        "sarmiento": "sarmiento junin", "talleres": "talleres cordoba", "union": "union de santa fe",
    },
    "super league": {
        "aek athens": "aek", "aris thessaloniki": "aris", "kifisia fc": "kifisia",
        "levadiakos": "levadeiakos", "nfc volos": "volos nfc", "olympiacos": "olympiakos",
        "paok thessaloniki": "paok",
    },
})
ALIASES_EXTRA["jupiler pro league"].update({"sporting charleroi": "charleroi", "union st gilloise": "st gilloise"})
ALIASES_EXTRA["la liga 2"].update({"ad ceuta fc": "ceuta"})
ALIASES_EXTRA["bundesliga"].update({"fc heidenheim": "heidenheim"})

ALIASES_EXTRA["2 bundesliga"].update({"fc heidenheim": "heidenheim"})
ALIASES_EXTRA["jupiler pro league"].update({"lommel": "lommel sk"})

# Final /new/ archive countries. Only observed current-provider spellings with
# a single literal candidate in the matching country/league table are listed.
ALIASES_EXTRA.update({
    "chinese super league": {
        "henan": "henan songshan longmen", "shenzhen peng city": "shenzhen xinpengcheng",
        "zhejiang": "zhejiang professional",
    },
    "veikkausliiga": {"oulu": "ac oulu"},
    "irish premier division": {
        "st patrick s athletic": "st patricks", "st patricks athletic": "st patricks",
        "drogheda united": "drogheda", "galway united": "galway",
    },
    "eliteserien": {"hamarkameratene": "hamkam", "kfum": "kfum oslo"},
    "swiss super league": {"fc vaduz": "vaduz", "fc zurich": "zurich", "grasshopper": "grasshoppers"},
})

# API-Football final-result labels observed on 2026-11-07 (fixture date
# 2026-11-06). Each target was checked against ONE existing literal club
# identity in its reviewed historical league. No fuzzy matching at runtime.
ALIASES_EXTRA["romanian superliga"].update({
    "petrolul ploiesti": "petrolul", "arges pitesti": "fc arges",
})
ALIASES_EXTRA["russian premier league"].update({
    "lokomotiv": "lokomotiv moscow",
})
ALIASES_EXTRA["2 bundesliga"].update({
    "spvgg greuther furth": "greuther furth",
})
ALIASES_EXTRA["allsvenskan"].update({"hammarby ff": "hammarby"})
ALIASES_EXTRA["austrian bundesliga"].update({"rapid vienna": "sk rapid"})
ALIASES_EXTRA["ligue 2"].update({"red star fc 93": "red star"})
ALIASES_EXTRA["ekstraklasa"].update({"cracovia krakow": "cracovia"})
# Swiss Challenge League has no comparable reviewed historical candidate
# in this source set; SC Kriens / FC Aarau / Stade Nyonnais remain blocked.
