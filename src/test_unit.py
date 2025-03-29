import os
import time
import pytest
import uuid
import aiofiles
from fastapi.testclient import TestClient
from api import app, model  # Import your FastAPI app

client = TestClient(app)  # Create a test client

### ✅ Test Model Initialization
def test_model_load():
    assert model is not None
    
### ✅ Test API Response for /analyze
@pytest.mark.asyncio
async def test_api_transcription():
    """Test the API with a test audio"""
    with open("../test/test4.mp3", "rb") as f:
        audio_data = f.read()
    response = client.post("/analyze", files={"file": ("test4.mp3", audio_data, "audio/mpeg")})
    assert response.status_code == 200
    json_data = response.json()
    assert "transcription" in json_data
    assert f'{json_data["transcription"]}'.strip() == "Hello world."
    assert "latency" in json_data
    assert json_data["latency"] >= 0  # Should return a valid latency

### ✅ Test API Stats Endpoint
def test_api_stats():
    """Ensure stats endpoint returns correct stats."""
    response = client.get("/stats")
    assert response.status_code == 200
    json_data = response.json()
    
    assert "total_calls" in json_data
    assert "median_latency" in json_data
    assert "average_audio_length" in json_data

### ✅ Test Stats Update
@pytest.mark.asyncio
async def test_stats_tracking():
    """Ensure that after calling `/analyze`, stats are updated."""
    response_old = client.get("/stats")
    json_data_old = response_old.json()
    with open("../test/test4.mp3", "rb") as f:
        audio_data = f.read()
    postnew = client.post("/analyze", files={"file": ("test4.mp3", audio_data, "audio/mpeg")})
    assert postnew.status_code == 200
    response_new = client.get("/stats")
    assert response_new.status_code == 200
    json_data_new = response_new.json()
    assert json_data_new["total_calls"] > json_data_old["total_calls"]