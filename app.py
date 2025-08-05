"""
Flask METAR Reader Web Application

A web application that fetches METAR (aviation weather reports) from airports
and converts them from cryptic aviation codes into human-readable weather reports.

Author: Generated with Claude Code
License: MIT
"""

from flask import Flask, render_template, request
import requests
import re

app = Flask(__name__)

class METARDecoder:
    """
    A class to decode METAR weather reports into human-readable format.
    
    METAR is a standardized weather reporting format used in aviation.
    This decoder converts cryptic codes into plain English descriptions.
    """
    
    def __init__(self):
        """Initialize the decoder with wind direction mappings."""
        # Map compass direction abbreviations to full names
        self.wind_directions = {
            'N': 'north', 'NNE': 'north-northeast', 'NE': 'northeast', 'ENE': 'east-northeast',
            'E': 'east', 'ESE': 'east-southeast', 'SE': 'southeast', 'SSE': 'south-southeast',
            'S': 'south', 'SSW': 'south-southwest', 'SW': 'southwest', 'WSW': 'west-southwest',
            'W': 'west', 'WNW': 'west-northwest', 'NW': 'northwest', 'NNW': 'north-northwest'
        }
    
    def get_wind_direction_text(self, degrees):
        """
        Convert wind direction in degrees to human-readable compass direction.
        
        Args:
            degrees (int): Wind direction in degrees (0-360)
            
        Returns:
            str: Human-readable wind direction (e.g., 'north', 'southwest')
        """
        if degrees == 0 or degrees == 360:
            return 'north'
        
        # 16-point compass rose directions
        directions = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 
                     'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
        
        # Each direction covers 22.5 degrees (360/16)
        index = round(degrees / 22.5) % 16
        return self.wind_directions[directions[index]]
    
    def decode_visibility(self, vis_str):
        """
        Decode visibility information from METAR format.
        
        Args:
            vis_str (str): Visibility string from METAR (e.g., '10SM', '5SM')
            
        Returns:
            str: Human-readable visibility description
        """
        if vis_str == '10SM' or vis_str.endswith('SM'):
            miles = vis_str.replace('SM', '')  # Remove 'SM' (statute miles) suffix
            if miles == '10' or int(miles) >= 10:
                return "10+ miles visibility"
            return f"{miles} miles visibility"
        return "visibility not reported"
    
    def decode_clouds(self, cloud_str):
        """
        Decode cloud coverage and altitude information.
        
        Args:
            cloud_str (str): Cloud information from METAR (e.g., 'SCT015', 'BKN025')
            
        Returns:
            str: Human-readable cloud description with altitude if applicable
        """
        # Standard cloud coverage codes
        cloud_types = {
            'CLR': 'clear skies',           # Clear below 12,000 ft
            'SKC': 'sky clear',             # Sky clear (automated stations)
            'FEW': 'few clouds',            # 1-2 oktas (1/8-2/8 coverage)
            'SCT': 'scattered clouds',      # 3-4 oktas (3/8-4/8 coverage)
            'BKN': 'broken clouds',         # 5-7 oktas (5/8-7/8 coverage)
            'OVC': 'overcast'              # 8 oktas (full coverage)
        }
        
        for code, description in cloud_types.items():
            if cloud_str.startswith(code):
                # Clear/sky clear conditions don't have altitude
                if code in ['CLR', 'SKC']:
                    return description
                
                # Extract altitude (3 digits representing hundreds of feet)
                altitude_match = re.search(r'(\d{3})', cloud_str)
                if altitude_match:
                    altitude = int(altitude_match.group(1)) * 100  # Convert to actual feet
                    return f"{description} at {altitude} feet"
                return description
                
        return "cloud conditions not reported"
    
    def decode_weather_phenomena(self, wx_str):
        """
        Decode weather phenomena and precipitation types.
        
        Args:
            wx_str (str): Weather phenomena string (e.g., '-RA', '+TSRA', 'VCFG')
            
        Returns:
            str or None: Human-readable weather description, None if no phenomena found
        """
        # Common weather phenomena codes
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
        
        result = []
        for code, desc in phenomena.items():
            if code in wx_str:
                intensity_prefix = ''
                # Check for intensity modifiers
                if wx_str.startswith('-'):
                    intensity_prefix = 'light '
                elif wx_str.startswith('+'):
                    intensity_prefix = 'heavy '
                elif wx_str.startswith('VC'):
                    intensity_prefix = 'nearby '
                    
                result.append(f"{intensity_prefix}{desc}")
        
        return ', '.join(result) if result else None
    
    def celsius_to_fahrenheit(self, celsius):
        """
        Convert temperature from Celsius to Fahrenheit.
        
        Args:
            celsius (int): Temperature in Celsius
            
        Returns:
            int: Temperature in Fahrenheit, rounded to nearest degree
        """
        return round((celsius * 9/5) + 32)
    
    def decode_metar(self, metar_string):
        """
        Main method to decode a complete METAR string into human-readable format.
        
        Args:
            metar_string (str): Complete METAR weather report string
            
        Returns:
            dict: Dictionary containing summary, detailed breakdown, and raw METAR
        """
        parts = metar_string.split()
        
        # Initialize decoded weather information structure
        decoded = {
            'station': '',       # Airport identifier
            'time': '',         # Observation time
            'wind': '',         # Wind conditions
            'visibility': '',   # Visibility distance
            'weather': '',      # Weather phenomena
            'clouds': '',       # Cloud coverage
            'temperature': '',  # Current temperature
            'dewpoint': '',     # Dewpoint temperature
            'pressure': ''      # Barometric pressure
        }
        
        if not parts:
            return "Unable to decode METAR"
        
        # First element is always the station identifier (e.g., KHIO)
        decoded['station'] = parts[0]
        
        # Parse each component of the METAR string
        for part in parts:
            # Time stamp: DDHHMMZ format (day, hour, minute, Zulu time)
            if re.match(r'\d{6}Z', part):
                day = part[:2]
                hour = part[2:4] 
                minute = part[4:6]
                decoded['time'] = f"Observed at {hour}:{minute}Z on day {day}"
            
            # Wind information: DDDSSKT (direction in degrees, speed in knots)
            elif re.match(r'\d{3}\d{2}KT', part) or re.match(r'VRB\d{2}KT', part):
                if part.startswith('VRB'):  # Variable wind direction
                    speed = part[3:5]
                    decoded['wind'] = f"Variable wind at {speed} knots"
                else:
                    direction = int(part[:3])  # Wind direction in degrees
                    speed = int(part[3:5])     # Wind speed in knots
                    wind_dir_text = self.get_wind_direction_text(direction)
                    decoded['wind'] = f"Wind from the {wind_dir_text} at {speed} knots"
            
            # Visibility in statute miles
            elif part.endswith('SM'):
                decoded['visibility'] = self.decode_visibility(part)
            
            # Weather phenomena (rain, snow, fog, etc.)
            elif any(wx in part for wx in ['RA', 'SN', 'DZ', 'FG', 'BR', 'HZ', 'TS', 'SH']):
                weather = self.decode_weather_phenomena(part)
                if weather:
                    decoded['weather'] = weather
            
            # Cloud coverage and altitude
            elif any(part.startswith(cloud) for cloud in ['CLR', 'SKC', 'FEW', 'SCT', 'BKN', 'OVC']):
                decoded['clouds'] = self.decode_clouds(part)
            
            # Temperature and dewpoint: TT/DD format (M prefix indicates negative)
            elif re.match(r'M?\d{2}/M?\d{2}', part):
                temps = part.split('/')
                # Convert 'M' prefix to negative sign for below-zero temperatures
                temp_c = int(temps[0].replace('M', '-'))
                dew_c = int(temps[1].replace('M', '-'))
                
                # Convert to Fahrenheit for US users
                temp_f = self.celsius_to_fahrenheit(temp_c)
                dew_f = self.celsius_to_fahrenheit(dew_c)
                
                decoded['temperature'] = f"{temp_f}°F ({temp_c}°C)"
                decoded['dewpoint'] = f"Dewpoint {dew_f}°F ({dew_c}°C)"
            
            # Altimeter setting: ATTTT format (inches of mercury * 100)
            elif part.startswith('A') and len(part) == 5:
                # Convert from hundredths to actual inHg (e.g., A3012 -> 30.12)
                pressure_inhg = float(part[1:3] + '.' + part[3:5])
                decoded['pressure'] = f"Pressure {pressure_inhg} inHg"
        
        # Build a concise weather summary for display
        summary_parts = []
        
        # Prioritize active weather phenomena, otherwise show sky conditions
        if decoded['weather']:
            summary_parts.append(decoded['weather'])
        elif decoded['clouds']:
            summary_parts.append(decoded['clouds'])
        
        # Always include temperature if available
        if decoded['temperature']:
            summary_parts.append(decoded['temperature'])
        
        # Include wind conditions
        if decoded['wind']:
            summary_parts.append(decoded['wind'])
        
        summary = ', '.join(summary_parts) if summary_parts else "Weather conditions available"
        
        return {
            'summary': summary,      # Brief, user-friendly summary
            'details': decoded,      # Complete breakdown of all elements
            'raw_metar': metar_string  # Original METAR for reference
        }

def fetch_metar(airport_code):
    """
    Fetch METAR data from the Aviation Weather Center API.
    
    Args:
        airport_code (str): 4-letter ICAO airport identifier (e.g., 'KHIO')
        
    Returns:
        str or None: Raw METAR string if successful, None if failed or no data
    """
    # Aviation Weather Center METAR API endpoint
    url = f"https://aviationweather.gov/api/data/metar?ids={airport_code.upper()}"
    
    try:
        # Make HTTP request with reasonable timeout
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # Raise exception for HTTP errors
        
        metar_data = response.text.strip()
        
        # Check if we received valid METAR data
        if not metar_data or metar_data.lower().startswith('no metar'):
            return None
            
        return metar_data
        
    except requests.RequestException:
        # Handle network errors, timeouts, HTTP errors, etc.
        return None

# Flask route handlers

@app.route('/')
def index():
    """
    Home page - displays the airport code input form.
    
    Returns:
        str: Rendered HTML template for the main page
    """
    return render_template('index.html')

@app.route('/metar', methods=['POST'])
def get_metar():
    """
    Process METAR request - fetch and decode weather data for submitted airport.
    
    Returns:
        str: Rendered HTML template with weather results or error message
    """
    # Get and clean airport code from form submission
    airport_code = request.form.get('airport_code', '').strip().upper()
    
    # Validate input
    if not airport_code:
        return render_template('index.html', error="Please enter an airport code")
    
    # ICAO airport codes are always 4 characters
    if len(airport_code) != 4:
        return render_template('index.html', error="Airport code must be 4 characters (e.g., KHIO)")
    
    # Fetch raw METAR data from API
    metar_raw = fetch_metar(airport_code)
    
    if not metar_raw:
        return render_template('index.html', 
                             error=f"Could not fetch METAR for {airport_code}. Please check the airport code.")
    
    # Decode METAR into human-readable format
    decoder = METARDecoder()
    decoded_metar = decoder.decode_metar(metar_raw)
    
    # Display results
    return render_template('result.html', 
                         airport_code=airport_code,
                         decoded=decoded_metar)

# Application entry point
if __name__ == '__main__':
    # Run the Flask development server
    # Note: For production deployment, use a proper WSGI server like Gunicorn
    app.run(debug=True, host='127.0.0.1', port=5000)