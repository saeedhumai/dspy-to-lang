import aiohttp
import base64
from fastapi import HTTPException
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage



class ImageProcessor:
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm

    async def download_image(self, image_url: str) -> bytes:
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as response:
                if response.status != 200:
                    raise HTTPException(status_code=400, detail="Failed to download image")
                return await response.read()

    async def process_image(self, image_url: str) -> str:
        try:
            message = HumanMessage(
                content=[
                    {"type": "text", "text": "Please analyze this image and do the following: \n\n"
                                              "1. If it's a prescription, extract the medicine names, dosages, and instructions.\n"
                                          "2. If it's a medicine package, identify the medicine name."},
                {"type": "image_url", "image_url": {"url": image_url}},
                ],
            )
            response = self.llm.invoke([message])
            print(response.content)

            # Call the model directly instead of using chain
            # response = await self.llm.ainvoke(messages)
            return response.content
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Image processing failed: {str(e)}")