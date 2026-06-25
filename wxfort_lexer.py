import re
import sys
import os
import csv
import random
from dataclasses import dataclass
from typing import List


# ─────────────────────────────────────────────────────────────────
#  TOKEN DEFINITIONS
# ─────────────────────────────────────────────────────────────────

@dataclass
class Token:
    token_class: str
    lexeme: str
    value: object
    line: int
    column: int

    def __str__(self):
        return (f"  Line {self.line:>2}, Col {self.column:>2}  |  "
                f"{self.token_class:<12}|  lexeme: {self.lexeme:<20}|  value: {self.value}")


# ── Keyword table (checked FIRST — always wins over other classes) ─
KEYWORDS = {
    "STATION", "DATE", "TIME", "TEMP", "HUMID", "WIND",
    "COND", "FCST", "PRESSURE", "VISIBILITY", "DEWPOINT",
    "REPORT", "END", "BEGIN", "ALERT", "UNIT"
}

# ── Condition vocabulary (closed set, no overlap with KEYWORDS) ───
CONDITIONS = {
    "SUNNY", "CLOUDY", "RAIN", "STORM", "FOGGY",
    "HEATWAVE", "SNOW", "CLEAR", "OVERCAST", "DRIZZLE",
    "BLIZZARD", "THUNDERSTORM", "HAIL", "WINDY"
}

# ── Direction vocabulary (ordered longest-first for greedy match) ──
DIRECTIONS = [
    "NORTH", "SOUTH", "EAST", "WEST",
    "NNE", "NNW", "SSE", "SSW",
    "NE", "NW", "SE", "SW",
    "N", "S", "E", "W"
]
DIRECTION_SET = set(DIRECTIONS)

# ── Unit map for MEASURE tokens ───────────────────────────────────
UNIT_MAP = {
    "C":   "CELSIUS",
    "F":   "FAHRENHEIT",
    "K":   "KELVIN",
    "KPH": "KPH",
    "MPH": "MPH",
    "HPA": "HECTOPASCAL",
    "MB":  "MILLIBAR",
    "MM":  "MILLIMETRE",
    "KM":  "KILOMETRE",
    "M":   "METRE",
}

CONDITIONS_LIST = list(CONDITIONS)


# ─────────────────────────────────────────────────────────────────
#  REGULAR EXPRESSIONS  (compiled once, applied in priority order)
# ─────────────────────────────────────────────────────────────────

RE_COMMENT     = re.compile(r'^(C\s.*|C$|!.*)')
RE_STRING      = re.compile(r'"([^"]*)"')
RE_TIMEREF     = re.compile(r'\b((?:[01]\d|2[0-3])[0-5]\d(?:Z|UTC)|DAY[1-9])\b')
RE_MEASURE_PCT = re.compile(r'\b(\d+(?:\.\d+)?)(%)')
RE_MEASURE     = re.compile(r'\b(\d+(?:\.\d+)?)(KPH|MPH|HPA|MB|MM|KM|C|F|K|M)\b')
RE_FLOAT       = re.compile(r'\b(\d+\.\d+)\b')
RE_INTEGER     = re.compile(r'\b(\d+)\b')
RE_DATE        = re.compile(r'\b(\d{4}-\d{2}-\d{2})\b')
RE_WORD        = re.compile(r'\b([A-Z][A-Z0-9\-]*)\b')
RE_OPERATOR    = re.compile(r'([=<>!+\-*/,;:()\[\]{}])')


# ─────────────────────────────────────────────────────────────────
#  WEATHER SOURCE GENERATOR
# ─────────────────────────────────────────────────────────────────

def _seed_rng(city: dict) -> random.Random:
    """Deterministic RNG seeded from city data so results are consistent."""
    seed_str = city["code"] + city["country"] + city["lat"] + city["lon"]
    return random.Random(hash(seed_str) & 0xFFFFFFFF)

def generate_weather_source(city: dict) -> str:
    """
    Generate a WXFORT-formatted weather report for the given city row.
    Weather values are deterministically seeded from city coordinates.
    """
    rng = _seed_rng(city)

    lat  = float(city["lat"])
    lon  = float(city["lon"])

    # Temperature baseline by latitude band
    abs_lat = abs(lat)
    if abs_lat < 15:
        temp_base = rng.uniform(28, 38)   # tropical
    elif abs_lat < 35:
        temp_base = rng.uniform(18, 32)   # subtropical / South Asia / MENA
    elif abs_lat < 55:
        temp_base = rng.uniform(5, 20)    # temperate
    else:
        temp_base = rng.uniform(-15, 5)   # polar / subarctic

    temp    = round(temp_base, 1)
    dewp    = round(temp - rng.uniform(3, 12), 1)
    humid   = rng.randint(35, 92)
    press   = rng.randint(998, 1025)
    vis     = round(rng.uniform(3.0, 15.0), 1)
    w_spd   = rng.randint(5, 45)
    wind    = rng.choice(DIRECTIONS)
    cond    = rng.choice(CONDITIONS_LIST)

    # Observation time
    hour    = rng.randint(0, 23)
    minute  = rng.choice(["00", "15", "30", "45"])
    obs_t   = f"{hour:02d}{minute}Z"

    # Forecast (6 hrs later)
    fcst_h  = (hour + 6) % 24
    fcst_t  = f"{fcst_h:02d}{minute}Z"
    fcst_c  = rng.choice(CONDITIONS_LIST)
    fcst_T  = round(temp + rng.uniform(-3, 5), 1)
    fcst_w  = rng.choice(DIRECTIONS)
    fcst_s  = rng.randint(5, 50)

    station_id = f"{city['code']}-{city['iata']}"
    date       = "2026-05-10"

    alert_map = {
        "HEATWAVE":     '"EXTREME HEAT ADVISORY IN EFFECT"',
        "BLIZZARD":     '"BLIZZARD WARNING ISSUED"',
        "STORM":        '"SEVERE STORM WATCH ACTIVE"',
        "THUNDERSTORM": '"SEVERE THUNDERSTORM WARNING"',
    }
    alert_line = f"\n  ALERT   {alert_map[cond]}" if cond in alert_map else ""

    source = f"""\
C  WXFORT Weather Forecast - {city['city']}, {city['country']}
STATION {station_id}
DATE    {date}
! Observation time in Zulu (ICAO standard)
TIME    {obs_t}

BEGIN OBSERVATION
  TEMP        {temp}C
  DEWPOINT    {dewp}C
  HUMID       {humid}%
  PRESSURE    {press}HPA
  VISIBILITY  {vis}KM
  WIND        {wind} {w_spd}KPH
  COND        {cond}
END OBSERVATION

BEGIN FORECAST
  TIME    {fcst_t}
  TEMP    {fcst_T}C
  WIND    {fcst_w} {fcst_s}KPH
  COND    {fcst_c}{alert_line}
END FORECAST

C  End of report DAY1
"""
    return source


# ─────────────────────────────────────────────────────────────────
#  CITY LOADER
# ─────────────────────────────────────────────────────────────────

def load_cities(csv_path: str) -> list:
    """Load cities from cities.csv. Returns list of dicts."""
    if not os.path.isfile(csv_path):
        print(f"  ERROR: cities.csv not found at '{csv_path}'")
        print("  Make sure cities.csv is in the same folder as this script.")
        sys.exit(1)
    cities = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cities.append({k.strip(): v.strip() for k, v in row.items()})
    return cities


def select_city(cities: list) -> dict:
    """
    Interactive terminal city selector.
    Supports search by city name or country code, then numeric selection.
    """
    sep = "─" * 64

    while True:
        print(f"\n{sep}")
        print(f"  WXFORT — City Selection  ({len(cities)} cities available)")
        print(sep)
        query = input("  Search city or country code (or press Enter to list all): ").strip().upper()

        if query:
            matches = [
                c for c in cities
                if query in c["city"].upper() or query == c["country"].upper() or query == c["code"].upper()
            ]
        else:
            matches = cities

        if not matches:
            print(f"\n  No cities found for '{query}'. Try again.\n")
            continue

        # Display results in columns of 3
        print(f"\n  Found {len(matches)} result(s):\n")
        col_w = 22
        for i, c in enumerate(matches):
            label = f"[{i+1:>3}] {c['city']} ({c['country']}·{c['code']})"
            end = "\n" if (i + 1) % 3 == 0 or i == len(matches) - 1 else ""
            print(f"  {label:<{col_w*2}}", end=end)

        print(f"\n{sep}")

        raw = input("  Enter number to select, or 0 to search again: ").strip()
        if not raw.isdigit():
            continue
        idx = int(raw)
        if idx == 0:
            continue
        if 1 <= idx <= len(matches):
            return matches[idx - 1]
        print("  Invalid number, try again.")


# ─────────────────────────────────────────────────────────────────
#  LEXER ENGINE
# ─────────────────────────────────────────────────────────────────

class WXFORTLexer:
    """
    Single-pass lexical analyser for WXFORT source files.

    Assumptions:
      - Input is uppercase ASCII (FORTRAN convention).
      - One statement per line; no continuation lines or nested blocks.
      - Tokens are separated by whitespace or operator characters.
      - Lines beginning with 'C ' (or 'C' alone) or '!' are comments.
      - The file extension .wxf is a naming convention only.
    """

    def __init__(self):
        self.tokens: List[Token] = []
        self.errors: List[str]   = []

    # ── Public entry points ───────────────────────────────────────
    def tokenise_file(self, filepath: str) -> List[Token]:
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"Source file not found: {filepath}")
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()
        return self.tokenise(source)

    def tokenise(self, source: str) -> List[Token]:
        self.tokens = []
        self.errors = []
        for lineno, raw_line in enumerate(source.splitlines(), start=1):
            line = raw_line.strip()
            if line:
                self._scan_line(line, lineno)
        return self.tokens

    # ── Line scanner (single pass, position pointer) ──────────────
    def _scan_line(self, line: str, lineno: int):
        if RE_COMMENT.match(line):
            self.tokens.append(Token("COMMENT", line, line, lineno, 1))
            return

        pos    = 0
        length = len(line)

        while pos < length:
            if line[pos].isspace():
                pos += 1
                continue

            col = pos + 1  # 1-based

            m = RE_STRING.match(line, pos)
            if m:
                self.tokens.append(Token("STRING", m.group(0), m.group(1), lineno, col))
                pos = m.end(); continue

            m = RE_DATE.match(line, pos)
            if m:
                self.tokens.append(Token("DATE", m.group(1), m.group(1), lineno, col))
                pos = m.end(); continue

            m = RE_TIMEREF.match(line, pos)
            if m:
                lex = m.group(1)
                if lex.startswith("DAY"):
                    val = ("RELATIVE_DAY", int(lex[3:]))
                else:
                    suffix    = "ZULU" if lex.endswith("Z") else "UTC"
                    time_part = lex[:-1] if lex.endswith("Z") else lex[:-3]
                    val       = (time_part, suffix)
                self.tokens.append(Token("TIMEREF", lex, val, lineno, col))
                pos = m.end(); continue

            m = RE_MEASURE_PCT.match(line, pos)
            if m:
                num_str = m.group(1)
                num_val = float(num_str) if '.' in num_str else int(num_str)
                self.tokens.append(Token("MEASURE", m.group(0), (num_val, "PERCENT"), lineno, col))
                pos = m.end(); continue

            m = RE_MEASURE.match(line, pos)
            if m:
                num_str, unit = m.group(1), m.group(2)
                num_val = float(num_str) if '.' in num_str else int(num_str)
                self.tokens.append(Token("MEASURE", m.group(0), (num_val, UNIT_MAP.get(unit, unit)), lineno, col))
                pos = m.end(); continue

            m = RE_FLOAT.match(line, pos)
            if m:
                self.tokens.append(Token("FLOAT", m.group(1), float(m.group(1)), lineno, col))
                pos = m.end(); continue

            m = RE_INTEGER.match(line, pos)
            if m:
                self.tokens.append(Token("INTEGER", m.group(1), int(m.group(1)), lineno, col))
                pos = m.end(); continue

            m = RE_WORD.match(line, pos)
            if m:
                lex = m.group(1)
                if lex in KEYWORDS:
                    cls = "KEYWORD"
                elif lex in DIRECTION_SET:
                    cls = "DIRECTION"
                elif lex in CONDITIONS:
                    cls = "CONDITION"
                else:
                    cls = "IDENTIFIER"
                self.tokens.append(Token(cls, lex, lex, lineno, col))
                pos = m.end(); continue

            m = RE_OPERATOR.match(line, pos)
            if m:
                self.tokens.append(Token("OPERATOR", m.group(1), m.group(1), lineno, col))
                pos = m.end(); continue

            self.errors.append(f"Line {lineno}, Col {col}: Unrecognised character '{line[pos]}'")
            pos += 1

    # ── Display ───────────────────────────────────────────────────
    def print_tokens(self):
        sep = "-" * 76
        print(sep)
        print(f"  {'Line/Col':<16}| {'TOKEN CLASS':<12}| {'LEXEME':<22}| VALUE")
        print(sep)
        for tok in self.tokens:
            print(tok)
        print(sep)
        print(f"  Total tokens: {len(self.tokens)}")
        if self.errors:
            print("\n  LEXICAL ERRORS:")
            for e in self.errors:
                print(f"    {e}")

    def get_summary(self) -> dict:
        s = {}
        for tok in self.tokens:
            s[tok.token_class] = s.get(tok.token_class, 0) + 1
        return s
    
# ─────────────────────────────────────────────────────────────────
#  Syntax Analyzer
# ─────────────────────────────────────────────────────────────────

class WXFORTSyntaxAnalyzer:
    def __init__(self):
        self.errors = []

    def validate(self, tokens):
        i = 0
        n = len(tokens)

        def tok():
            return tokens[i] if i < n else None

        def expect_lexeme(expected):
            nonlocal i
            if i >= n:
                self.errors.append(f"Expected {expected}, but reached end of file")
                return False

            if tokens[i].lexeme != expected:
                self.errors.append(
                    f"Expected '{expected}', found '{tokens[i].lexeme}' "
                    f"at Line {tokens[i].line}, Col {tokens[i].column}"
                )
                return False

            i += 1
            return True

        # ── HEADER ─────────────────────────────
        if not expect_lexeme("STATION"): return False
        if tok() and tok().token_class == "IDENTIFIER":
            i += 1
        else:
            self.errors.append("Missing station identifier")
            return False

        if not expect_lexeme("DATE"): return False
        if tok() and tok().token_class == "DATE":
            i += 1
        else:
            self.errors.append("Missing date value")
            return False

        if not expect_lexeme("TIME"): return False
        if tok() and tok().token_class == "TIMEREF":
            i += 1
        else:
            self.errors.append("Missing time value")
            return False

        # ── OBSERVATION ─────────────────────────
        if not expect_lexeme("BEGIN"): return False
        if not expect_lexeme("OBSERVATION"): return False

        # skip observation content safely
        while i < n and not (tokens[i].lexeme == "END"):
            i += 1

        if not expect_lexeme("END"): return False
        if not expect_lexeme("OBSERVATION"): return False

        # ── FORECAST ────────────────────────────
        if not expect_lexeme("BEGIN"): return False
        if not expect_lexeme("FORECAST"): return False

        while i < n and not (tokens[i].lexeme == "END"):
            i += 1

        if not expect_lexeme("END"): return False
        if not expect_lexeme("FORECAST"): return False

        # ── FINAL END ───────────────────────────
        if not expect_lexeme("END"): return False

        return True

    def print_errors(self):
        if not self.errors:
            print("SYNTAX: VALID ✔")
        else:
            print("SYNTAX ERRORS:")
            for e in self.errors:
                print(" ", e)

# ─────────────────────────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────────────────────────

def main():
    lexer    = WXFORTLexer()
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Mode 1: explicit .wxf file passed as argument 
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
        print(f"\nWXFORT Lexical Analyser  |  scanning: {filepath}\n")
        try:
            lexer.tokenise_file(filepath)
        except FileNotFoundError as e:
            print(e); sys.exit(1)

    # Mode 2: city selector from cities.csv 
    else:
        csv_path = os.path.join(script_dir, "cities.csv")
        cities   = load_cities(csv_path)
        city     = select_city(cities)

        print(f"\n{'='*60}")
        print(f"  Selected: {city['city']}, {city['country']}  "
              f"({city['iata']} / ICAO: {city['iata']})")
        print(f"{'='*60}")

        source = generate_weather_source(city)

        print("\nINPUT SOURCE (generated .wxf):")
        print("=" * 60)
        print(source)

        lexer.tokenise(source)

        parser = WXFORTSyntaxAnalyzer()
        is_valid = parser.validate(lexer.tokens)

        parser.print_errors()

        if parser.errors:
            print("SYNTAX: INVALID ❌")
        else:
            print("SYNTAX: VALID ✔")

        print(f"\nDEBUG: tokens processed = {len(lexer.tokens)}")
        print(f"DEBUG: syntax errors = {len(parser.errors)}")

    print("=" * 60)
    print("TOKEN STREAM OUTPUT:")
    print("=" * 60)
    lexer.print_tokens()

    print("\nTOKEN CLASS SUMMARY:")
    print("-" * 30)
    for cls, count in sorted(lexer.get_summary().items()):
        print(f"  {cls:<14}: {count}")
    print("-" * 30)
    print(f"  {'TOTAL':<14}: {len(lexer.tokens)}")

    # Offer another city
    if len(sys.argv) == 1:
        print()
        again = input("  Analyse another city? (y/n): ").strip().lower()
        if again == "y":
            main()


if __name__ == "__main__":
    main()