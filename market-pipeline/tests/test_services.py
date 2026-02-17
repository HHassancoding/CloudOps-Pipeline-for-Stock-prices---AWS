"""Tests for service layer functions."""
import pytest
from unittest.mock import patch, MagicMock
from app.services import fetch_price, collect_once, check_anomaly
from app.models import validate_symbol, SYMBOL_TO_ID
import requests


class TestValidateSymbol:
    """Test symbol validation."""
    
    def test_valid_symbol_uppercase(self):
        """Test validation with uppercase symbol."""
        assert validate_symbol("BTC") == "BTC"
        assert validate_symbol("ETH") == "ETH"
    
    def test_valid_symbol_lowercase(self):
        """Test validation with lowercase symbol."""
        assert validate_symbol("btc") == "BTC"
        assert validate_symbol("eth") == "ETH"
    
    def test_valid_symbol_mixed_case(self):
        """Test validation with mixed case symbol."""
        assert validate_symbol("bTc") == "BTC"
        assert validate_symbol("eTh") == "ETH"
    
    def test_invalid_symbol(self):
        """Test validation with invalid symbol."""
        with pytest.raises(ValueError) as exc_info:
            validate_symbol("INVALID")
        assert "Unsupported symbol" in str(exc_info.value)
        assert "INVALID" in str(exc_info.value)


class TestFetchPrice:
    """Test price fetching from CoinGecko API."""
    
    @patch('app.services.requests.get')
    def test_fetch_price_btc_success(self, mock_get):
        """Test successful BTC price fetch."""
        # Mock API response
        mock_response = MagicMock()
        mock_response.json.return_value = {"bitcoin": {"usd": 50000.0}}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        price = fetch_price("BTC")
        
        assert price == 50000.0
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert call_args[1]['params']['ids'] == 'bitcoin'
        assert call_args[1]['params']['vs_currencies'] == 'usd'
    
    @patch('app.services.requests.get')
    def test_fetch_price_eth_success(self, mock_get):
        """Test successful ETH price fetch."""
        # Mock API response
        mock_response = MagicMock()
        mock_response.json.return_value = {"ethereum": {"usd": 3000.0}}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        price = fetch_price("ETH")
        
        assert price == 3000.0
        call_args = mock_get.call_args
        assert call_args[1]['params']['ids'] == 'ethereum'
    
    @patch('app.services.requests.get')
    def test_fetch_price_invalid_symbol(self, mock_get):
        """Test fetch price with invalid symbol."""
        with pytest.raises(ValueError) as exc_info:
            fetch_price("INVALID")
        assert "Unsupported symbol" in str(exc_info.value)
        mock_get.assert_not_called()
    
    @patch('app.services.requests.get')
    def test_fetch_price_timeout(self, mock_get):
        """Test fetch price with timeout error."""
        mock_get.side_effect = requests.exceptions.Timeout()
        
        with pytest.raises(requests.RequestException) as exc_info:
            fetch_price("BTC")
        assert "Timeout" in str(exc_info.value)
    
    @patch('app.services.requests.get')
    def test_fetch_price_api_error(self, mock_get):
        """Test fetch price with API error."""
        mock_get.side_effect = requests.exceptions.RequestException("API Error")
        
        with pytest.raises(requests.RequestException) as exc_info:
            fetch_price("BTC")
        assert "Failed to fetch price" in str(exc_info.value)
    
    @patch('app.services.requests.get')
    def test_fetch_price_no_data_in_response(self, mock_get):
        """Test fetch price when API returns no data for symbol."""
        mock_response = MagicMock()
        mock_response.json.return_value = {}  # Empty response
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        with pytest.raises(ValueError) as exc_info:
            fetch_price("BTC")
        assert "No price data returned" in str(exc_info.value)


class TestCollectOnce:
    """Test collect_once function."""
    
    @patch('app.services.fetch_price')
    @patch('app.services.add_price_point')
    def test_collect_once_success(self, mock_add, mock_fetch):
        """Test successful price collection."""
        from app.models import PricePoint
        from datetime import datetime
        
        # Mock fetch_price to return a price
        mock_fetch.return_value = 50000.0
        
        # Mock add_price_point to return a PricePoint
        mock_point = PricePoint(
            id=1,
            timestamp=datetime.utcnow(),
            price=50000.0,
            symbol="BTC"
        )
        mock_add.return_value = mock_point
        
        result = collect_once("BTC")
        
        assert result.symbol == "BTC"
        assert result.price == 50000.0
        mock_fetch.assert_called_once_with("BTC")
        mock_add.assert_called_once_with(50000.0, "BTC")
    
    @patch('app.services.fetch_price')
    def test_collect_once_invalid_symbol(self, mock_fetch):
        """Test collect_once with invalid symbol."""
        with pytest.raises(ValueError):
            collect_once("INVALID")
        mock_fetch.assert_not_called()


class TestCheckAnomaly:
    """Test anomaly detection function."""
    
    @patch('app.services.get_last_two')
    def test_check_anomaly_insufficient_data(self, mock_get_last_two):
        """Test anomaly check with insufficient data."""
        mock_get_last_two.return_value = []
        
        result = check_anomaly("BTC")
        
        assert result["anomaly"] is False
        assert result["message"] == "Not enough data points"
        assert result["symbol"] == "BTC"
    
    @patch('app.services.get_last_two')
    def test_check_anomaly_no_anomaly(self, mock_get_last_two):
        """Test anomaly check with no anomaly detected."""
        from app.models import PricePoint
        from datetime import datetime
        
        # Mock two price points with small difference
        mock_get_last_two.return_value = [
            PricePoint(id=2, timestamp=datetime.utcnow(), price=50050.0, symbol="BTC"),
            PricePoint(id=1, timestamp=datetime.utcnow(), price=50000.0, symbol="BTC"),
        ]
        
        result = check_anomaly("BTC")
        
        assert result["anomaly"] is False
        assert result["symbol"] == "BTC"
        assert result["latest_price"] == 50050.0
        assert result["second_last_price"] == 50000.0
        assert result["price_difference"] == 50.0
    
    @patch('app.services.get_last_two')
    def test_check_anomaly_with_anomaly(self, mock_get_last_two):
        """Test anomaly check with anomaly detected."""
        from app.models import PricePoint
        from datetime import datetime
        
        # Mock two price points with large difference (>100)
        mock_get_last_two.return_value = [
            PricePoint(id=2, timestamp=datetime.utcnow(), price=51000.0, symbol="BTC"),
            PricePoint(id=1, timestamp=datetime.utcnow(), price=50000.0, symbol="BTC"),
        ]
        
        result = check_anomaly("BTC")
        
        assert result["anomaly"] is True
        assert result["symbol"] == "BTC"
        assert result["latest_price"] == 51000.0
        assert result["second_last_price"] == 50000.0
        assert result["price_difference"] == 1000.0
