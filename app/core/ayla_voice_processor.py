from google.cloud import speech
from configs.logger import logger
import re

class AudioProcessor:
    def __init__(self, path_secret: str):
        from google.oauth2 import service_account

        credentials = service_account.Credentials.from_service_account_file(path_secret)
        self.client = speech.SpeechClient(credentials=credentials)

    def _convert_to_gcs_uri(self, url: str) -> str | None:
        """Converts a storage.googleapis.com URL to a gs:// URI.

        Args:
            url: The URL to convert.

        Returns:
            The gs:// URI, or None if the URL is not in the expected format.
        """
        match = re.match(r"https://storage\.googleapis\.com/(.*)", url)
        if match:
            gcs_path = match.group(1)
            return f"gs://{gcs_path}"
        else:
            return None # or handle the invalid URL case differently (e.g., raise an exception)

    async def transcribe_audio(self, audio_url: str) -> str:
        gcs_uri = self._convert_to_gcs_uri(audio_url)
        audio = speech.RecognitionAudio(uri=gcs_uri)
        logger.info("Audio URL: " + gcs_uri)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.MP3,
            sample_rate_hertz=16000,
            language_code="en-US",
        )

        response = self.client.recognize(config=config, audio=audio)
        
        # Collect all transcriptions
        full_transcript = ""
        for result in response.results:
            full_transcript += result.alternatives[0].transcript + " "  # Concatenate all results
        
        logger.info("Transcript: " + full_transcript.strip())
        return full_transcript.strip()