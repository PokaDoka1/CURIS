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
    def __init__(self, type, message, command, context):
            self.type = type
            self.message = message
            self.command = command
            self.context = context

    type: FailureType
    message: str
    command: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

def _print_failure(failure):
    print("Failure Type: " + str(failure.type) + "\n")
    print("Failure Message: " + str(failure.message) + "\n")
    print("Failure Command: " + str(failure.command) + "\n")
    print("Failure Context" + str(failure.context) + "\n")

class AgentFailureDetector:
    # search_dict searches the dictionary to get all the model_responses
    # this function is achieved through recursion
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

    # this function calls search_dict to gather all the model_responses into an array
    def extract_model_responses(self, json_file):
        model_responses = []
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        self.search_dict(data, model_responses)
        return model_responses

    def _get_strategic_failure(self, response):
        response_text = response.get('value').lower()
        response_text_lower = response_text.lower()

        confusion_indicators = [
            "i apologize",
            "cannot",
            "unable to",
            "error",
            "failed",
            "doesn't work",
            "incorrect"
        ]

        for indicator in confusion_indicators:
            if indicator in response_text_lower:
                return response_text
        return None

    def analyze_interaction(self, response):
        # Analyzing a single interaction for confusion
        strategic_failure = self._get_strategic_failure(response)

        if self._get_strategic_failure(response) != None:
            return Failure(
                type = FailureType.STRATEGIC,
                message = "Agent exhibited confusion",
                command = "",
                context = {'response': strategic_failure}
            )
        return None

    def store_responses(self, model_responses):
        with open('model_responses.txt', 'a') as file: 
            for response in model_responses: 
                file.write(str(response) + "\n\n")

def main():
    detector = AgentFailureDetector()
    model_responses = detector.extract_model_responses('agent_data.json')
    
    for response in model_responses:
        failure = detector.analyze_interaction(response)
        if (failure != None):
            _print_failure(failure)
            print("\n")


main()


