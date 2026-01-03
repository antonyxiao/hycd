import sys
import json
import requests
from urllib.parse import quote

def get_guanhua_readings(char):
    """
    Scrapes the '官話' (Mandarin) readings for a given Chinese character from zi.tools API.
    """
    encoded_char = quote(char)
    url = f"https://zi.tools/api/zi/{encoded_char}"
    
    headers = {
        'User-Agent': 'curl/7.88.1',
        'Accept': 'application/json'
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        try:
            data = response.json()
        except json.JSONDecodeError:
            print(f"Error: Response was not valid JSON.", file=sys.stderr)
            return []
            
    except requests.RequestException as e:
        print(f"Error fetching URL for {char}: {e}", file=sys.stderr)
        return []

    readings = set()
    
    # Navigate to yi -> yin -> rows
    try:
        yi_data = data.get('yi', {})
        yin_data = yi_data.get('yin', {})
        rows = yin_data.get('rows', {})
        
        for key, value in rows.items():
            # Keys for Mandarin seem to start with "cn:"
            # e.g., "cn:鋟_jian1"
            if key.startswith("cn:"):
                # Extract reading from value usually has 'syl' and 'ton'
                syl = value.get('syl')
                ton = value.get('ton')
                
                if syl and ton:
                    reading = f"{syl}{ton}"
                    readings.add(reading)
                elif "_" in key:
                    # Fallback to key parsing if fields missing
                    parts = key.split('_')
                    if len(parts) >= 2:
                        readings.add(parts[-1])
                        
    except Exception as e:
        print(f"Error processing data for {char}: {e}", file=sys.stderr)
        return []

    return sorted(list(readings))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scrape_zi_tools.py <character>")
        sys.exit(1)

    char = sys.argv[1]
    readings = get_guanhua_readings(char)
    
    if readings:
        print(f"Readings for {char}: {', '.join(readings)}")
    else:
        print(f"No 官話 readings found for {char}")
