from fastapi import HTTPException
import requests
import tempfile
import os
from configs.logger import logger
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader

class AylaDocumentProcessor:
    def __init__(self):
        """Initialize document processor"""
        pass   
    def process_document(self, url: str) -> str:
        # Step 1: Download the document
        response = requests.get(url)
        
        # Determine file type from url
        if url.lower().endswith('.pdf'):
            logger.info("Processing PDF document")
            file_extension = ".pdf"
            loader_class = PyPDFLoader
        elif url.lower().endswith('.docx'):
            logger.info("Processing DOCX document")
            file_extension = ".docx"
            loader_class = Docx2txtLoader
        else:
            logger.error("Unsupported file type. Only PDF and DOCX are supported.")
            raise HTTPException(status_code=400, detail="Unsupported file type. Only PDF and DOCX are supported.")

        # Create temporary file and save downloaded content
        with tempfile.NamedTemporaryFile(suffix=file_extension, delete=False) as temp_file:
            temp_file.write(response.content)
            temp_path = temp_file.name

        try:
            # Step 2: Load and process the document
            loader = loader_class(temp_path)
            document = loader.load()
            document_content = document[0].page_content
            logger.info(f"Document content: {document_content}")
            return document_content
        finally:
            # Clean up temporary file
            if os.path.exists(temp_path):
                os.remove(temp_path)