from typing import Dict, Any
import aiohttp
from configs.settings import Settings
from configs.logger import logger

class DimaHttpClient:
    def __init__(self, settings: Settings):
        self.base_url = settings.DIMA_SERVICE_URL
        self.headers = {
            "Content-Type": "application/json"
            # Add any other required headers here
        }
        
    async def search_medicines(self, message: Dict[str, Any]) -> list:
        """Send search request to Dima service for a single medicine."""
        
        logger.info(f"Sending message to Dima service: {message}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.base_url,  # API endpoint
                    headers=self.headers,  # HTTP headers
                    json=message,  # Request payload
                ) as response:
                    
                    logger.info(f"Dima service URL: {self.base_url}")
                    logger.info(f"Response status from Dima service: {response.status}")

                    # Handle successful responses
                    if response.status == 200 or response.status == 201:
                        response_data = await response.json()
                        return response_data
                    
                    # Handle specific error cases
                    elif response.status == 400:
                        error_data = await response.json()
                        logger.error(f"Bad Request to Dima service: {error_data}")
                        raise ValueError(f"Bad request to Dima service: {error_data}")
                    
                    elif response.status == 408:
                        logger.error("Request timeout to Dima service")
                        raise TimeoutError("Request timeout to Dima service")
                    
                    else:
                        # Log unexpected status codes with detailed response text
                        error_text = await response.text()
                        logger.error(f"Unexpected response from Dima service: Status {response.status}, Response: {error_text}")
                        raise Exception(f"Failed to call Dima service: {response.status}, Response: {error_text}")
        
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error occurred while calling Dima service: {str(e)}")
            raise ConnectionError(f"HTTP error occurred: {str(e)}")
        
        except Exception as e:
            logger.error(f"General error occurred while calling Dima service: {str(e)}")
            raise RuntimeError(f"Error calling Dima service: {str(e)}")
