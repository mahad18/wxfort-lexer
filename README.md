# WXFORT — Weather Forecasting Lexical Analyser

A domain-specific language and lexical analyser inspired by FORTRAN's classic data-card syntax, built for **CT-367 Theory of Programming Languages**.

WXFORT (Weather Forecasting FORTRAN) represents meteorological observation and forecast data in a structured, uppercase, FORTRAN-style format. The lexer tokenizes `.wxf` source text into a stream of classified tokens using a single-pass, priority-ordered regex scanner.

## Why This Project Stands Out

Most lexer assignments tokenize generic arithmetic expressions. WXFORT instead defines **4 novel token classes** that don't exist in any general-purpose language lexer:

| Token Class | Purpose | Example |
|---|---|---|
| `MEASURE` | Fuses a number + meteorological unit | `42.3C` → `(42.3, 'CELSIUS')` |
| `TIMEREF` | ICAO Zulu/UTC time validation | `0600Z` → `('0600', 'ZULU')` |
| `DIRECTION` | Longest-match compass bearings | `NNE`, `SW`, `N` |
| `CONDITION` | Closed weather vocabulary | `HEATWAVE`, `STORM` |

The core engineering challenge: resolving ambiguity like `42.3C` (is `C` a unit or an identifier?) and `0600Z` (don't split into integer `0600` + identifier `Z`) — solved purely through regex priority ordering, with no external parsing libraries.

## Features

- Single-pass, regex-based lexer (Python standard library only — `re`, `csv`, `dataclasses`)
- 207-city real-world dataset (`cities.csv`) used to deterministically generate weather reports by coordinates
- 16 reserved keywords, 14 weather conditions, 16 compass directions
- Line/column-accurate token stream output
- Reproducible: same city → same generated WXFORT source every time

## How It Works

1. `load_cities()` reads `cities.csv` and lets you select a city
2. `generate_weather_source()` deterministically generates a `.wxf` report based on the city's latitude/longitude (climate zone) using a seeded RNG
3. `WXFORTLexer.tokenise()` scans the generated source line-by-line, matching each position against compiled regexes in strict priority order
4. The full token stream (class, lexeme, value, line, column) is printed to the terminal

## Sample Input (`.wxf`)

```
C WXFORT Weather Forecast - Karachi, PK
STATION KHI-OPKC
DATE 2026-05-10
TIME 0600Z
BEGIN OBSERVATION
TEMP 42.3C
HUMID 78%
WIND NNE 18KPH
COND HEATWAVE
ALERT "EXTREME HEAT ADVISORY IN EFFECT"
END OBSERVATION
```

## Sample Output

```
Line  Col  Token Class   Lexeme       Value
2     1    KEYWORD       STATION      STATION
2     9    IDENTIFIER    KHI-OPKC     KHI-OPKC
3     1    KEYWORD       DATE         DATE
3     9    DATE          2026-05-10   2026-05-10
5     9    TIMEREF       0600Z        ('0600', 'ZULU')
8     15   MEASURE       42.3C        (42.3, 'CELSIUS')
10    15   MEASURE       78%          (78, 'PERCENT')
13    15   DIRECTION     NNE          NNE
14    15   CONDITION     HEATWAVE     HEATWAVE
```

## Running It

Requires Python 3 (standard library only — no dependencies to install).

```bash
git clone https://github.com/<your-username>/wxfort-lexer.git
cd wxfort-lexer
python wxfort_lexer.py
```

Follow the terminal prompts to search and select a city from the dataset — the lexer will generate a weather report for it and print the full token stream.

## Project Structure

```
wxfort-lexer/
├── wxfort_lexer.py     # Core lexer + city-based source generator
├── cities.csv          # 207-city dataset (name, country, code, IATA, lat, lon)
└── README.md
```

## Assumptions & Limitations

- Input must be uppercase ASCII (mirrors FORTRAN punch-card convention)
- One statement per line, no continuation lines
- `MEASURE` requires the unit to be directly adjacent to the number (`42.3C`, not `42.3 C`)
- `TIMEREF` requires a `Z` or `UTC` suffix
- This is a lexer + simple syntax checker — full grammar/block validation (e.g. matching `BEGIN`/`END`) is out of scope

## Authors

Built for CT-367 Theory of Programming Languages, Department of Computer Science & Information Technology, NED University of Engineering & Technology, Karachi.

- Mahad Ahmed
- M. Usman Sheikh
- M. Hamdan Abid
- Syed Mohtashim Ali
