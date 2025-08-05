from flask import Flask, render_template, request, jsonify
import requests
import re
from datetime import datetime

app = Flask(__name__)

class METARDecoder:
    def __init__(self):
        self.wind_directions = {
            'N': 'north', 'NNE': 'north-northeast', 'NE': 'northeast', 'ENE': 'east-northeast',
            'E': 'east', 'ESE': 'east-southeast', 'SE': 'southeast', 'SSE': 'south-southeast',
            'S': 'south', 'SSW': 'south-southwest', 'SW': 'southwest', 'WSW': 'west-southwest',
            'W': 'west', 'WNW': 'west-northwest', 'NW': 'northwest', 'NNW': 'north-northwest'
        }
    
    def get_wind_direction_text(self, degrees):
        if degrees == 0 or degrees == 360:
            return 'north'
        directions = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
        index = round(degrees / 22.5) % 16
        return self.wind_directions[directions[index]]
    
    def decode_visibility(self, vis_str):
        if vis_str == '10SM' or vis_str.endswith('SM'):
            miles = vis_str.replace('SM', '')
            if miles == '10' or int(miles) >= 10:
                return "10+ miles visibility"
            return f"{miles} miles visibility"
        return "visibility not reported"
    
    def decode_clouds(self, cloud_str):
        cloud_types = {
            'CLR': 'clear skies',
            'SKC': 'sky clear',
            'FEW': 'few clouds',
            'SCT': 'scattered clouds',
            'BKN': 'broken clouds',
            'OVC': 'overcast'
        }
        
        for code, description in cloud_types.items():
            if cloud_str.startswith(code):
                if code in ['CLR', 'SKC']:
                    return description
                altitude_match = re.search(r'(\d{3})', cloud_str)
                if altitude_match:
                    altitude = int(altitude_match.group(1)) * 100
                    return f"{description} at {altitude} feet"
                return description
        return "cloud conditions not reported"
    
    def decode_weather_phenomena(self, wx_str):
        phenomena = {
            'RA': 'rain',
            'SN': 'snow',
            'DZ': 'drizzle',
            'FG': 'fog',
            'BR': 'mist',
            'HZ': 'haze',
            'TS': 'thunderstorm',
            'SH': 'showers'
        }
        
        intensity = {
            '-': 'light ',
            '+': 'heavy ',
            'VC': 'in vicinity '
        }
        
        result = []
        for code, desc in phenomena.items():
            if code in wx_str:
                intensity_prefix = ''
                if wx_str.startswith('-'):
                    intensity_prefix = 'light '
                elif wx_str.startswith('+'):
                    intensity_prefix = 'heavy '
                elif wx_str.startswith('VC'):
                    intensity_prefix = 'nearby '
                result.append(f"{intensity_prefix}{desc}")
        
        return ', '.join(result) if result else None
    
    def celsius_to_fahrenheit(self, celsius):
        return round((celsius * 9/5) + 32)
    
    def decode_metar(self, metar_string):
        parts = metar_string.split()
        decoded = {
            'station': '',
            'time': '',
            'wind': '',
            'visibility': '',
            'weather': '',
            'clouds': '',
            'temperature': '',
            'dewpoint': '',
            'pressure': ''
        }
        
        if not parts:
            return "Unable to decode METAR"
        
        decoded['station'] = parts[0]
        
        for i, part in enumerate(parts):
            if re.match(r'\d{6}Z', part):
                day = part[:2]
                hour = part[2:4]
                minute = part[4:6]
                decoded['time'] = f"Observed at {hour}:{minute}Z on day {day}"
            
            elif re.match(r'\d{3}\d{2}KT', part) or re.match(r'VRB\d{2}KT', part):
                if part.startswith('VRB'):
                    speed = part[3:5]
                    decoded['wind'] = f"Variable wind at {speed} knots"
                else:
                    direction = int(part[:3])
                    speed = int(part[3:5])
                    wind_dir_text = self.get_wind_direction_text(direction)
                    decoded['wind'] = f"Wind from the {wind_dir_text} at {speed} knots"
            
            elif part.endswith('SM'):
                decoded['visibility'] = self.decode_visibility(part)
            
            elif any(wx in part for wx in ['RA', 'SN', 'DZ', 'FG', 'BR', 'HZ', 'TS', 'SH']):
                weather = self.decode_weather_phenomena(part)
                if weather:
                    decoded['weather'] = weather
            
            elif any(part.startswith(cloud) for cloud in ['CLR', 'SKC', 'FEW', 'SCT', 'BKN', 'OVC']):
                decoded['clouds'] = self.decode_clouds(part)
            
            elif re.match(r'M?\d{2}/M?\d{2}', part):
                temps = part.split('/')
                temp_c = int(temps[0].replace('M', '-'))
                dew_c = int(temps[1].replace('M', '-'))
                temp_f = self.celsius_to_fahrenheit(temp_c)
                dew_f = self.celsius_to_fahrenheit(dew_c)
                decoded['temperature'] = f"{temp_f}°F ({temp_c}°C)"
                decoded['dewpoint'] = f"Dewpoint {dew_f}°F ({dew_c}°C)"
            
            elif part.startswith('A') and len(part) == 5:
                pressure_inhg = float(part[1:3] + '.' + part[3:5])
                decoded['pressure'] = f"Pressure {pressure_inhg} inHg"
        
        summary_parts = []
        if decoded['weather']:
            summary_parts.append(decoded['weather'])
        elif decoded['clouds']:
            summary_parts.append(decoded['clouds'])
        
        if decoded['temperature']:
            summary_parts.append(decoded['temperature'])
        
        if decoded['wind']:
            summary_parts.append(decoded['wind'])
        
        summary = ', '.join(summary_parts) if summary_parts else "Weather conditions available"
        
        return {
            'summary': summary,
            'details': decoded,
            'raw_metar': metar_string
        }

def fetch_metar(airport_code):
    url = f"https://aviationweather.gov/api/data/metar?ids={airport_code.upper()}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        metar_data = response.text.strip()
        if not metar_data or metar_data.lower().startswith('no metar'):
            return None
        return metar_data
    except requests.RequestException:
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/metar', methods=['POST'])
def get_metar():
    airport_code = request.form.get('airport_code', '').strip().upper()
    
    if not airport_code:
        return render_template('index.html', error="Please enter an airport code")
    
    if len(airport_code) != 4:
        return render_template('index.html', error="Airport code must be 4 characters (e.g., KHIO)")
    
    metar_raw = fetch_metar(airport_code)
    
    if not metar_raw:
        return render_template('index.html', error=f"Could not fetch METAR for {airport_code}. Please check the airport code.")
    
    decoder = METARDecoder()
    decoded_metar = decoder.decode_metar(metar_raw)
    
    return render_template('result.html', 
                         airport_code=airport_code,
                         decoded=decoded_metar)

if __name__ == '__main__':
    app.run(debug=True)