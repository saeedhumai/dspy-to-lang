from app.core.diana_http_client import DianaHttpClient
from configs.settings import Settings

test_conv_init_payload = {
  "user_id": "674850197227b000090d5c3f",
  "user_whatsapp_phone_number": "+14155238886",
  "user_name": "John Doe",
  "user_address": "Al quoz street - 12 27th St - Dubai, UAE",
  "ayla_conversation_id": "674850197227b000090d5c3f",
  "medicine_names": [
    "Rhinase"
  ]
}

test_order_init_payload = {
  "user_whatsapp_phone_number": "+14177398109",
  "user_delivery_phone_number": "+14155238886",
  "user_name": "John Doe",
  "user_address": "Charsadda, Pakistan",
  "follow_up_diana_conversation_id": "674850197227b000090d5c3f",
  "user_additional_instructions": "Please deliver to the address: Charsadda, Pakistan"
}

if __name__ == "__main__":
    import asyncio
    diana_client = DianaHttpClient(settings=Settings())

    asyncio.run(diana_client.process_whatsapp_inquiry(test_conv_init_payload))
    # asyncio.run(diana_client.initiate_order_inquiry(test_order_init_payload))

