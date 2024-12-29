from langchain.chains import LLMChain
from langchain_openai import ChatOpenAI
from app.prompts.rfq_prompts import RFQPromptManager
from app.chains.rfq_parser import RFQOutputParser
from typing import Dict, List

class RFQChain:
    def __init__(self, llm_model: str = "gpt-4-1106-preview"):
        self.llm = ChatOpenAI(
            model=llm_model,
            temperature=0,
            streaming=True
        )
        self.prompt_manager = RFQPromptManager()
        self.parser = RFQOutputParser()
        
        self.chain = LLMChain(
            llm=self.llm,
            prompt=self.prompt_manager.prompt,
            output_parser=self.parser,
            verbose=True
        )

    async def process(
        self,
        input_text: str,
        chat_history: List[Dict],
        status: str,
        context: Dict
    ) -> Dict:
        """Process user input and return structured RFQ response"""
        response = await self.chain.ainvoke({
            "input": input_text,
            "chat_history": chat_history,
            "status": status,
            **context
        })
        
        parsed_response = self.parser.parse(response)
        
        # Auto-set ready_for_rfq if all required fields complete
        if parsed_response.is_ready() and "complete" in parsed_response.status.lower():
            parsed_response.ready_for_rfq = True
            
        return parsed_response.dict()