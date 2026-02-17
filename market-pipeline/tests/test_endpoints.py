"""Tests for FastAPI endpoints."""
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient


class TestCollectOnceEndpoint:
    """Test POST /collect-once/{symbol} endpoint."""
    
    @patch('app.services.fetch_price')
    def test_collect_once_btc_success(self, mock_fetch, client):
        """Test successful BTC price collection."""
        mock_fetch.return_value = 50000.0
        
        response = client.post("/collect-once/BTC")
        
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "BTC"
        assert data["price"] == 50000.0
        assert "timestamp" in data
        assert "id" in data
    
    @patch('app.services.fetch_price')
    def test_collect_once_eth_success(self, mock_fetch, client):
        """Test successful ETH price collection."""
        mock_fetch.return_value = 3000.0
        
        response = client.post("/collect-once/ETH")
        
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "ETH"
        assert data["price"] == 3000.0
    
    @patch('app.services.fetch_price')
    def test_collect_once_lowercase_symbol(self, mock_fetch, client):
        """Test price collection with lowercase symbol."""
        mock_fetch.return_value = 50000.0
        
        response = client.post("/collect-once/btc")
        
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "BTC"
    
    def test_collect_once_invalid_symbol(self, client):
        """Test price collection with invalid symbol."""
        response = client.post("/collect-once/INVALID")
        
        assert response.status_code == 400
        data = response.json()
        assert "Unsupported symbol" in data["detail"]
    
    @patch('app.services.fetch_price')
    def test_collect_once_api_timeout(self, mock_fetch, client):
        """Test price collection with API timeout."""
        import requests
        mock_fetch.side_effect = requests.RequestException("Timeout")
        
        response = client.post("/collect-once/BTC")
        
        assert response.status_code == 503
        data = response.json()
        assert "External API error" in data["detail"]


class TestHistoryEndpoint:
    """Test GET /history/{symbol} endpoint."""
    
    @patch('app.services.fetch_price')
    def test_history_btc_empty(self, mock_fetch, client):
        """Test history endpoint with no data."""
        response = client.get("/history/BTC")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0
    
    @patch('app.services.fetch_price')
    def test_history_btc_with_data(self, mock_fetch, client):
        """Test history endpoint with collected data."""
        mock_fetch.return_value = 50000.0
        
        # Collect some data points
        client.post("/collect-once/BTC")
        client.post("/collect-once/BTC")
        
        response = client.get("/history/BTC")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert all(item["symbol"] == "BTC" for item in data)
    
    @patch('app.services.fetch_price')
    def test_history_limit_parameter(self, mock_fetch, client):
        """Test history endpoint with limit parameter."""
        mock_fetch.return_value = 50000.0
        
        # Collect 5 data points
        for _ in range(5):
            client.post("/collect-once/BTC")
        
        response = client.get("/history/BTC?limit=3")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
    
    @patch('app.services.fetch_price')
    def test_history_separate_symbols(self, mock_fetch, client):
        """Test that different symbols have separate histories."""
        mock_fetch.return_value = 50000.0
        
        # Collect BTC and ETH
        client.post("/collect-once/BTC")
        client.post("/collect-once/BTC")
        client.post("/collect-once/ETH")
        
        btc_response = client.get("/history/BTC")
        eth_response = client.get("/history/ETH")
        
        assert len(btc_response.json()) == 2
        assert len(eth_response.json()) == 1
        assert all(item["symbol"] == "BTC" for item in btc_response.json())
        assert all(item["symbol"] == "ETH" for item in eth_response.json())
    
    def test_history_invalid_symbol(self, client):
        """Test history endpoint with invalid symbol."""
        response = client.get("/history/INVALID")
        
        assert response.status_code == 400
        data = response.json()
        assert "Unsupported symbol" in data["detail"]
    
    @patch('app.services.fetch_price')
    def test_history_lowercase_symbol(self, mock_fetch, client):
        """Test history endpoint with lowercase symbol."""
        mock_fetch.return_value = 50000.0
        client.post("/collect-once/BTC")
        
        response = client.get("/history/btc")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1


class TestAnomalyEndpoint:
    """Test GET /anomaly/{symbol} endpoint."""
    
    def test_anomaly_insufficient_data(self, client):
        """Test anomaly endpoint with no data."""
        response = client.get("/anomaly/BTC")
        
        assert response.status_code == 200
        data = response.json()
        assert data["anomaly"] is False
        assert data["message"] == "Not enough data points"
        assert data["symbol"] == "BTC"
    
    @patch('app.services.fetch_price')
    def test_anomaly_no_anomaly(self, mock_fetch, client):
        """Test anomaly endpoint with normal price changes."""
        # Collect two similar prices
        mock_fetch.return_value = 50000.0
        client.post("/collect-once/BTC")
        
        mock_fetch.return_value = 50050.0
        client.post("/collect-once/BTC")
        
        response = client.get("/anomaly/BTC")
        
        assert response.status_code == 200
        data = response.json()
        assert data["anomaly"] is False
        assert data["symbol"] == "BTC"
        assert "latest_price" in data
        assert "second_last_price" in data
        assert "price_difference" in data
    
    @patch('app.services.fetch_price')
    def test_anomaly_with_anomaly(self, mock_fetch, client):
        """Test anomaly endpoint with significant price change."""
        # Collect two prices with large difference (>100)
        mock_fetch.return_value = 50000.0
        client.post("/collect-once/BTC")
        
        mock_fetch.return_value = 51500.0
        client.post("/collect-once/BTC")
        
        response = client.get("/anomaly/BTC")
        
        assert response.status_code == 200
        data = response.json()
        assert data["anomaly"] is True
        assert data["symbol"] == "BTC"
        assert data["price_difference"] == 1500.0
    
    @patch('app.services.fetch_price')
    def test_anomaly_separate_symbols(self, mock_fetch, client):
        """Test that anomaly detection is symbol-specific."""
        # Collect BTC prices
        mock_fetch.return_value = 50000.0
        client.post("/collect-once/BTC")
        mock_fetch.return_value = 51500.0
        client.post("/collect-once/BTC")
        
        # Collect only one ETH price
        mock_fetch.return_value = 3000.0
        client.post("/collect-once/ETH")
        
        btc_response = client.get("/anomaly/BTC")
        eth_response = client.get("/anomaly/ETH")
        
        assert btc_response.json()["anomaly"] is True
        assert eth_response.json()["anomaly"] is False
        assert eth_response.json()["message"] == "Not enough data points"
    
    def test_anomaly_invalid_symbol(self, client):
        """Test anomaly endpoint with invalid symbol."""
        response = client.get("/anomaly/INVALID")
        
        assert response.status_code == 400
        data = response.json()
        assert "Unsupported symbol" in data["detail"]


class TestSupportedSymbolsEndpoint:
    """Test GET /supported-symbols endpoint."""
    
    def test_supported_symbols(self, client):
        """Test supported symbols endpoint."""
        response = client.get("/supported-symbols")
        
        assert response.status_code == 200
        data = response.json()
        assert "symbols" in data
        assert "mappings" in data
        assert isinstance(data["symbols"], list)
        assert isinstance(data["mappings"], dict)
        assert "BTC" in data["symbols"]
        assert "ETH" in data["symbols"]
        assert data["mappings"]["BTC"] == "bitcoin"
        assert data["mappings"]["ETH"] == "ethereum"
