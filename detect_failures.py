from inspect import ClassFoundException
import json
# using re to help me identify specific words within log data
import re

# using collections to count occurrences of items within a list
from collections import Counter
from enum import Enum
from typing import List, Optional, Dict, Any

class FailureType(Enum):
    EXECUTION = "execution"
    # Poor planing or execution (confusion)
    STRATEGIC = "strategic"
    LOOP = "loop"
    SYNTAX = "syntax"
    TIMEOUT = "timeout"
    ACCESS = "access"
    UNKNOWN = "unknown"

class Failure:
    type: FailureType
    message: str
    command: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

class AgentFailureDetector:
    def search_dict(self, data, responses):
            if isinstance(data, dict):
                for key, value in data.items():
                    if key == "model_response":
                        responses.append(value)
                    elif isinstance(value, (dict, list)):
                        self.search_dict(value, responses)
            elif isinstance(data, list):
                for item in data:
                    self.search_dict(item, responses)

            return responses

    def extract_model_responses(self, json_file):
        model_responses = []

        with open(json_file, 'r') as f:
            data = json.load(f)
        
        self.search_dict(data, model_responses)
            
        return model_responses

    # response should be a dictionary
    def _detect_strategic_failure(self, response: Dict):
        response_text = response.get('value', '').lower()

        confusion_indicators = [
            "i apologize",
            "cannot",
            "unable to",
            "error",
            "failed",
            "doesn't work",
            "incorrect"
        ]

        for indicator in response_text:
            if indicator in confusion_indicators:
                return True

    def analyze_interaction(self, iteraction_data: Dict):
        # Analyzing a single interaction for confusion
        model_response = iteraction_data.get('model_response', {})

        if self._detect_strategic_failure(model_response):
            return Failure(
                type = FailureType.STRATEGIC,
                message = "Agent exhibited confusion",
                context = {'response': model_response.get('value')}
            )
        return None

def main():
    print("Printing all of the model responses")
    detector = AgentFailureDetector()
    model_responses = detector.extract_model_responses('agent_data.json')
    for model_response in model_responses:
        print(model_response)
        print('\n\n')

main()


