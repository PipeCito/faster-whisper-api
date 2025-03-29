# Import required libraries
import time
import uuid
import aiofiles
import os
from fastapi import FastAPI, UploadFile, File
from faster_whisper import WhisperModel  # Faster implementation of Whisper speech-to-text
from pydub import AudioSegment  # Audio processing library
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

# Load InfluxDB configuration from environment variables
INFLUX_TOKEN = os.environ.get("INFLUX_TOKEN")
INFLUX_ORG = os.environ.get("INFLUX_ORG")
INFLUX_URL = os.environ.get("INFLUX_URL")
INFLUX_BUCKET = os.environ.get("INFLUX_BUCKET")

# NATS server connection string
NATS_SERVER = "nats://my-nats.default.svc.cluster.local:4222"

# Initialize InfluxDB client for metrics storage
client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
write_api = client.write_api()  # For writing metrics
query_api = client.query_api()  # For querying metrics

# Create FastAPI application instance
app = FastAPI()

# Initialize Whisper model for speech-to-text (small version for balance of speed/accuracy)
model = WhisperModel("small")

@app.post("/analyze")
async def analyze_audio(file: UploadFile = File(...)):
    """Endpoint to analyze audio files and return transcription with performance metrics"""
    start_time = time.time()  # Start timer for latency measurement
    
    # Generate unique filename for temporary storage
    unique_filename = f"audio/{uuid.uuid4()}.mp3"
    
    # Save uploaded file asynchronously in chunks (memory-efficient)
    async with aiofiles.open(unique_filename, "wb") as f:
        while chunk := await file.read(4096):  # Read in 4KB chunks
            await f.write(chunk)
    
    try:
        # Process the audio file
        audio = AudioSegment.from_file(unique_filename)
        duration = len(audio) / 1000  # Convert duration from ms to seconds
        
        # Transcribe audio using Whisper model
        segments, _ = model.transcribe(unique_filename)
        text_result = " ".join(segment.text for segment in segments)  # Combine all segments
        
    finally:
        # Clean up temporary file whether processing succeeds or fails
        os.remove(unique_filename)
    
    # Calculate processing latency
    latency = time.time() - start_time
    
    # Create metrics data point for InfluxDB
    point = (
        Point("audio_analysis")  # Measurement name
        .field("latency", latency)  # Processing time field
        .field("audio_length", duration)  # Audio duration field
        .time(time.time_ns(), WritePrecision.NS)  # Timestamp with nanosecond precision
    )
    
    # Write metrics to InfluxDB
    write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)
    
    # Return transcription and metrics to client
    return {
        "transcription": text_result,
        "latency": latency,
        "audio_length": duration
    }

@app.get("/stats")
def get_stats():
    """Endpoint to retrieve historical performance statistics"""
    # Flux query to get last 30 days of audio analysis metrics
    query = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: -30d)
      |> filter(fn: (r) => r._measurement == "audio_analysis")
    '''
    
    # Execute query and process results
    result = query_api.query(query=query)
    
    # Initialize metrics accumulators
    total_calls = 0
    latencies = []
    audio_lengths = []
    
    # Process query results
    for table in result:
        for record in table.records:
            if record.get_field() == "latency":
                latencies.append(record.get_value())
            elif record.get_field() == "audio_length":
                audio_lengths.append(record.get_value())
            total_calls += 1
    
    # Calculate statistics
    median_latency = sorted(latencies)[len(latencies) // 2] if latencies else 0
    avg_audio_length = sum(audio_lengths) / len(audio_lengths) if audio_lengths else 0
    
    return {
        "total_calls": total_calls/2, # One record per field is counted, so when a call is made, two records are created.
        "median_latency": median_latency,
        "average_audio_length": f"{avg_audio_length}s"  # Formatted as string with unit
    }

@app.get("/health")
async def health_check():
    #Simple health check endpoint for service monitoring
    return {"status": "ok"}
