import pytest
import unittest.mock as mock
from unittest.mock import patch
from app import METARDecoder, fetch_metar, app


class TestMETARDecoder:
    """Test suite for the METARDecoder class."""
    
    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.decoder = METARDecoder()
    
    def test_get_wind_direction_text(self):
        """Test wind direction conversion from degrees to text."""
        assert self.decoder.get_wind_direction_text(0) == 'north'
        assert self.decoder.get_wind_direction_text(360) == 'north'
        assert self.decoder.get_wind_direction_text(90) == 'east'
        assert self.decoder.get_wind_direction_text(180) == 'south'
        assert self.decoder.get_wind_direction_text(270) == 'west'
        assert self.decoder.get_wind_direction_text(45) == 'northeast'
        assert self.decoder.get_wind_direction_text(225) == 'southwest'
    
    def test_decode_visibility(self):
        """Test visibility decoding from METAR format."""
        assert self.decoder.decode_visibility('10SM') == '10+ miles visibility'
        assert self.decoder.decode_visibility('5SM') == '5 miles visibility'
        assert self.decoder.decode_visibility('1SM') == '1 miles visibility'
        assert self.decoder.decode_visibility('15SM') == '10+ miles visibility'
        assert self.decoder.decode_visibility('CAVOK') == 'visibility not reported'
    
    def test_decode_clouds(self):
        """Test cloud coverage and altitude decoding."""
        assert self.decoder.decode_clouds('CLR') == 'clear skies'
        assert self.decoder.decode_clouds('SKC') == 'sky clear'
        assert self.decoder.decode_clouds('FEW015') == 'few clouds at 1500 feet'
        assert self.decoder.decode_clouds('SCT025') == 'scattered clouds at 2500 feet'
        assert self.decoder.decode_clouds('BKN040') == 'broken clouds at 4000 feet'
        assert self.decoder.decode_clouds('OVC008') == 'overcast at 800 feet'
        assert self.decoder.decode_clouds('UNKNOWN') == 'cloud conditions not reported'
    
    def test_decode_weather_phenomena(self):
        """Test weather phenomena decoding."""
        assert self.decoder.decode_weather_phenomena('RA') == 'rain'
        assert self.decoder.decode_weather_phenomena('-RA') == 'light rain'
        assert self.decoder.decode_weather_phenomena('+RA') == 'heavy rain'
        assert self.decoder.decode_weather_phenomena('VCFG') == 'nearby fog'
        assert self.decoder.decode_weather_phenomena('TSRA') == 'rain, thunderstorm'
        assert self.decoder.decode_weather_phenomena('SN') == 'snow'
        assert self.decoder.decode_weather_phenomena('-SN') == 'light snow'
        assert self.decoder.decode_weather_phenomena('NOSUCH') is None
    
    def test_celsius_to_fahrenheit(self):
        """Test temperature conversion."""
        assert self.decoder.celsius_to_fahrenheit(0) == 32
        assert self.decoder.celsius_to_fahrenheit(100) == 212
        assert self.decoder.celsius_to_fahrenheit(-40) == -40
        assert self.decoder.celsius_to_fahrenheit(20) == 68
        assert self.decoder.celsius_to_fahrenheit(-10) == 14


class TestMETARDecodingIntegration:
    """Integration tests for complete METAR decoding."""
    
    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.decoder = METARDecoder()
    
    def test_decode_complete_metar_clear_weather(self):
        """Test decoding a complete METAR with clear weather."""
        metar = "KHIO 061853Z 27008KT 10SM CLR 22/16 A3012"
        result = self.decoder.decode_metar(metar)
        
        assert result['details']['station'] == 'KHIO'
        assert 'Observed at 18:53Z on day 06' in result['details']['time']
        assert 'Wind from the west at 8 knots' in result['details']['wind']
        assert result['details']['visibility'] == '10+ miles visibility'
        assert result['details']['clouds'] == 'clear skies'
        assert '72°F (22°C)' in result['details']['temperature']
        assert 'Dewpoint 61°F (16°C)' in result['details']['dewpoint']
        assert 'Pressure 30.12 inHg' in result['details']['pressure']
    
    def test_decode_metar_with_weather(self):
        """Test decoding METAR with active weather phenomena."""
        metar = "KORD 061851Z 09014KT 3SM -RA SCT008 BKN015 OVC025 18/17 A2992"
        result = self.decoder.decode_metar(metar)
        
        assert result['details']['station'] == 'KORD'
        assert 'Wind from the east at 14 knots' in result['details']['wind']
        assert result['details']['visibility'] == '3 miles visibility'
        assert result['details']['weather'] == 'light rain'
        assert 'overcast at 2500 feet' in result['details']['clouds']
        assert '64°F (18°C)' in result['details']['temperature']
    
    def test_decode_metar_variable_wind(self):
        """Test decoding METAR with variable wind direction."""
        metar = "KJFK 061851Z VRB05KT 10SM FEW250 25/20 A3008"
        result = self.decoder.decode_metar(metar)
        
        assert result['details']['wind'] == 'Variable wind at 05 knots'
        assert result['details']['visibility'] == '10+ miles visibility'
        assert 'few clouds at 25000 feet' in result['details']['clouds']
    
    def test_decode_metar_negative_temperatures(self):
        """Test decoding METAR with below-zero temperatures."""
        metar = "PANC 061853Z 36010KT 10SM CLR M15/M20 A2985"
        result = self.decoder.decode_metar(metar)
        
        assert '5°F (-15°C)' in result['details']['temperature']
        assert 'Dewpoint -4°F (-20°C)' in result['details']['dewpoint']
    
    def test_decode_metar_multiple_weather_phenomena(self):
        """Test decoding METAR with multiple weather conditions."""
        metar = "KBOS 061854Z 08015KT 2SM +TSRA BKN008 OVC020 20/19 A2995"
        result = self.decoder.decode_metar(metar)
        
        assert 'heavy rain, heavy thunderstorm' in result['details']['weather']
        assert result['details']['visibility'] == '2 miles visibility'
    
    def test_decode_empty_metar(self):
        """Test handling of empty or invalid METAR string."""
        result = self.decoder.decode_metar("")
        assert result == "Unable to decode METAR"
        
        result = self.decoder.decode_metar("   ")
        assert result == "Unable to decode METAR"


class TestFetchMETAR:
    """Test suite for METAR fetching functionality."""
    
    @patch('app.requests.get')
    def test_fetch_metar_success(self, mock_get):
        """Test successful METAR data fetching."""
        mock_response = mock.Mock()
        mock_response.text = "KHIO 061853Z 27008KT 10SM CLR 22/16 A3012"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = fetch_metar('KHIO')
        
        assert result == "KHIO 061853Z 27008KT 10SM CLR 22/16 A3012"
        mock_get.assert_called_once_with(
            "https://aviationweather.gov/api/data/metar?ids=KHIO", 
            timeout=10
        )
    
    @patch('app.requests.get')
    def test_fetch_metar_no_data(self, mock_get):
        """Test handling when no METAR data is available."""
        mock_response = mock.Mock()
        mock_response.text = "No METAR available"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = fetch_metar('ZZZZ')
        
        assert result is None
    
    @patch('app.requests.get')
    def test_fetch_metar_network_error(self, mock_get):
        """Test handling of network errors."""
        from requests.exceptions import RequestException
        mock_get.side_effect = RequestException("Network error")
        
        result = fetch_metar('KHIO')
        
        assert result is None
    
    @patch('app.requests.get')
    def test_fetch_metar_http_error(self, mock_get):
        """Test handling of HTTP errors."""
        mock_response = mock.Mock()
        from requests.exceptions import HTTPError
        mock_response.raise_for_status.side_effect = HTTPError("HTTP 404")
        mock_get.return_value = mock_response
        
        result = fetch_metar('INVALID')
        
        assert result is None
    
    @patch('app.requests.get')
    def test_fetch_metar_empty_response(self, mock_get):
        """Test handling of empty API response."""
        mock_response = mock.Mock()
        mock_response.text = "   "
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = fetch_metar('KHIO')
        
        assert result is None


class TestFlaskRoutes:
    """Test suite for Flask web application routes."""
    
    def setup_method(self):
        """Set up test fixtures before each test method."""
        app.config['TESTING'] = True
        self.client = app.test_client()
    
    def test_index_route(self):
        """Test the home page route."""
        response = self.client.get('/')
        
        assert response.status_code == 200
        assert b'html' in response.data.lower()
    
    @patch('app.fetch_metar')
    def test_metar_route_success(self, mock_fetch):
        """Test successful METAR request processing."""
        mock_fetch.return_value = "KHIO 061853Z 27008KT 10SM CLR 22/16 A3012"
        
        response = self.client.post('/metar', data={'airport_code': 'KHIO'})
        
        assert response.status_code == 200
        mock_fetch.assert_called_once_with('KHIO')
    
    def test_metar_route_empty_code(self):
        """Test METAR request with empty airport code."""
        response = self.client.post('/metar', data={'airport_code': ''})
        
        assert response.status_code == 200
        assert b'Please enter an airport code' in response.data
    
    def test_metar_route_invalid_length(self):
        """Test METAR request with invalid airport code length."""
        response = self.client.post('/metar', data={'airport_code': 'ABC'})
        
        assert response.status_code == 200
        assert b'Airport code must be 4 characters' in response.data
        
        response = self.client.post('/metar', data={'airport_code': 'ABCDE'})
        
        assert response.status_code == 200
        assert b'Airport code must be 4 characters' in response.data
    
    @patch('app.fetch_metar')
    def test_metar_route_fetch_failure(self, mock_fetch):
        """Test METAR request when data fetching fails."""
        mock_fetch.return_value = None
        
        response = self.client.post('/metar', data={'airport_code': 'ZZZZ'})
        
        assert response.status_code == 200
        assert b'Could not fetch METAR for ZZZZ' in response.data
    
    @patch('app.fetch_metar')
    def test_metar_route_lowercase_conversion(self, mock_fetch):
        """Test that lowercase airport codes are converted to uppercase."""
        mock_fetch.return_value = "KHIO 061853Z 27008KT 10SM CLR 22/16 A3012"
        
        response = self.client.post('/metar', data={'airport_code': 'khio'})
        
        assert response.status_code == 200
        mock_fetch.assert_called_once_with('KHIO')


class TestEdgeCases:
    """Test suite for edge cases and error conditions."""
    
    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.decoder = METARDecoder()
    
    def test_malformed_metar_parts(self):
        """Test handling of malformed METAR components."""
        # Missing components should not crash the decoder
        metar = "KHIO 061853Z INVALIDWIND INVALIDVIS"
        result = self.decoder.decode_metar(metar)
        
        assert isinstance(result, dict)
        assert result['details']['station'] == 'KHIO'
    
    def test_extreme_wind_directions(self):
        """Test edge cases for wind direction conversion."""
        # Test boundary conditions
        assert self.decoder.get_wind_direction_text(361) == 'north'  # Should wrap around
        assert self.decoder.get_wind_direction_text(-1) == 'north'  # Negative wrapping
    
    def test_unusual_visibility_values(self):
        """Test unusual visibility formats."""
        assert self.decoder.decode_visibility('0SM') == '0 miles visibility'
        assert self.decoder.decode_visibility('25SM') == '10+ miles visibility'
    
    def test_cloud_without_altitude(self):
        """Test cloud conditions without altitude information."""
        assert self.decoder.decode_clouds('FEW') == 'few clouds'
        assert self.decoder.decode_clouds('SCT') == 'scattered clouds'
    
    def test_temperature_conversion_edge_cases(self):
        """Test temperature conversion with extreme values."""
        assert self.decoder.celsius_to_fahrenheit(-273) == -459  # Absolute zero
        assert self.decoder.celsius_to_fahrenheit(1000) == 1832  # Very high temperature


if __name__ == '__main__':
    pytest.main([__file__])