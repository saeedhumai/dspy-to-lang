import aiohttp
import asyncio

url = "https://api.apify.com/v2/acts/mubash1r-humai~dima-agent/run-sync-get-dataset-items?token=apify_api_ruNrfgRgNf28e6VowDKCXCYNc6hEkm0gjIl4"

test_payload = {
    'pharmacy': 'lifepharmacy',
    'medicine_name': 'rhinase'
}

async def post_request():
    headers = {"Content-Type": "application/json"}  # Explicit headers
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=test_payload, headers=headers) as response:
                # Log response details for debugging
                try:
                    response.raise_for_status()
                    print("Response:", await response.json())
                except aiohttp.ClientError as e:
                    print("HTTP error:", e)
                    print("Response Text:", await response.text())  # Debugging response
    except Exception as e:
        print("An error occurred:", e)

# Ensure the event loop is managed correctly
if __name__ == "__main__":
    asyncio.run(post_request())
