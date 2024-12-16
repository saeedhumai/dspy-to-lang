import asyncio
from app.core.ayla_voice_processor import AudioProcessor

async def test_audio_processor():
    # Replace with your actual service account JSON path
    processor = AudioProcessor(r"configs\ayla_voice_creds.json")
    
    # Test case 1: Try with a real audio file in GCS
    audio_url = "gs://cloud-samples-data/speech/brooklyn_bridge.raw"
    audio_url = "gs://aisec-files-storage/files/123.mp3"
    audio_url = "gs://aisec-files-storage/files/1733495300487_voice_1733495299094.mp3"
    audio_url = "https://storage.googleapis.com/aisec-files-storage/files/1733495300487_voice_1733495299094.mp3"

    try:
        print("Testing audio transcription...")
        result = await processor.transcribe_audio(audio_url)
        print(f"Transcription result: {result}")
        
    except Exception as e:
        print(f"Error during transcription: {str(e)}")

if __name__ == "__main__":
    # Run the async test
    asyncio.run(test_audio_processor())