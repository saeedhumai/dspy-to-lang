from app.core.ayla_document_processor import AylaDocumentProcessor

def test_processor():
    # Initialize the processor
    processor = AylaDocumentProcessor()
    
    # URL of the document to process (replace with a valid URL for your tests)
    test_url = "https://storage.googleapis.com/aisec-files-storage/files/1733146498523_test_pdf.pdf"
    
    try:
        # Process the document
        content = processor.process_document(test_url)
        print("Processed Document Content:")
        print(content)
    except Exception as e:
        print(f"Error processing document: {e}")

if __name__ == "__main__":
    test_processor()