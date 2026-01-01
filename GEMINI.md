# Chinese Dictionary & Anki Deck Generator

## Project Overview
This project contains a suite of Python scripts and web assets designed to process Chinese dictionary data. Its primary purpose is to generate rich Anki flashcards for learning Chinese characters (Hanzi) and idioms (Chengyu). Additionally, it includes a simple web-based interface for character lookup and stroke order visualization.

## Key Features
*   **Hanzi Anki Deck Generator (`hyzd.py`):** Combines data from multiple sources (Xinhua Zidian, CC-CEDICT, and linguistic data) to create comprehensive flashcards. Cards include:
    *   Character (Traditional/Simplified)
    *   Pinyin & Jyutping (Cantonese)
    *   Middle Chinese reconstruction
    *   English & Chinese definitions
    *   Stroke count, Level, and Dictionary Page reference.
*   **Idiom Anki Deck Generator (`idioms_maker.py`):** Converts a JSON list of idioms into an Anki deck containing explanations, examples, and derivations.
*   **Web Dictionary (`index.html`):** A lightweight client-side dictionary that allows users to look up characters and view their stroke order animations (powered by `cnchar`).

## File Structure
*   **`hyzd.py`**: The main data processing script. It connects to a local MySQL database, processes CSV/text dictionaries (`xhzd.csv`, `cedict_ts.u8`), and creates `hanzi.apkg`.
*   **`idioms_maker.py`**: Reads `idiom.json` to generate `idoms.apkg`.
*   **`index.html` / `script.js`**: The frontend for the dictionary lookup tool.
*   **`char_detail.js`**: The JavaScript data file used by the web interface.
*   **`xhzd.csv` / `xhzd_corrected.csv`**: Source data from Xinhua Zidian.
*   **`cedict_ts.u8`**: CC-CEDICT dictionary data file.

## Setup & Usage

### Prerequisites
*   **Python 3.x**
*   **MySQL Database:** `hyzd.py` expects a local MySQL database named `hyzd` with specific credentials (see script for details).
*   **Python Dependencies:**
    ```bash
    pip install genanki pycantonese chinese_converter hanziconv mysql-connector-python
    ```

### Generating Decks
1.  **Hanzi Deck:**
    Ensure the database is running and all source files (`wiki.pkl`, `cedict_ts.u8`, `xhzd.csv`) are present.
    ```bash
    python hyzd.py
    ```
    This will generate `hanzi.apkg` and `jp_mc_en.pkl`.

2.  **Idioms Deck:**
    Ensure `idiom.json` is present.
    ```bash
    python idioms_maker.py
    ```
    This will generate `idoms.apkg`.

### Web Interface
Simply open `index.html` in a web browser. It serves as a standalone tool relying on `char_detail.js` and external CDNs for the `cnchar` library.
