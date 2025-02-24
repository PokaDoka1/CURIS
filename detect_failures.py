from inspect import ClassFoundException
import json
# using re to help me identify specific words within log data
import re

# using collections to count occurrences of items within a list
from collections import Counter
from enum import Enum
from typing import List, Optional, Dict, Any

class FailureType(Enum):
    EXECUTION = "Execution"
    # Poor planing or execution (confusion)
    STRATEGIC = "Strategic"
    LOOP = "Loop"
    SYNTAX = "Syntax"
    TIMEOUT = "Timeout"
    ACCESS = "Access"
    UNKNOWN = "Unknown"

class Failure:
    def __init__(self, type, message, command, context):
            self.type = type
            self.message = message
            self.command = command
            self.context = context

    type: str
    message: str
    command: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

def _print_failure(failure):
    print("Failure Type: " + str(failure.type) + "\n")
    print("Failure Message: " + str(failure.message) + "\n")
    print("Failure Command: " + str(failure.command) + "\n")
    print("Failure Context: " + str(failure.context) + "\n")

class AgentFailureDetector:
    # search_dict searches the dictionary to get all the model_responses
    # this function is achieved through recursion

    command_history = []

    def get_model_responses(self, data, responses):
        if isinstance(data, dict):
            for key, value in data.items():
                if key == "model_response":
                    responses.append(value)
                elif isinstance(value, (dict, list)):
                    self.get_model_responses(value, responses)
        elif isinstance(data, list):
            for item in data:
                self.get_model_responses(item, responses)

        return responses

    def get_commands(self, data, commands):
        if isinstance(data, dict):
            for key, value in data.items():
                # Look for "commands" key and add it to the list
                if key == "commands" and isinstance(value, list):
                    commands.extend(value)

                # Look for "execution_output" containing "command" -> "command_str"
                elif key == "execution_output" and isinstance(value, dict):
                    command = value.get("command")
                    if command:
                        command_str = command.get("command_str")
                        if command_str:
                            commands.append(command_str)

                # Recursively search deeper for both keys
                elif isinstance(value, (dict, list)):
                    self.get_commands(value, commands)

        elif isinstance(data, list):
            for item in data:
                self.get_commands(item, commands)

        return commands

    # this function calls search_dict to gather all the model_responses into an array
    def extract_model_responses(self, json_file):
        model_responses = []
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        self.get_model_responses(data, model_responses)
        return model_responses

    def extract_commands(self, json_file):
        commands = []
        with open(json_file, 'r') as f:
            data = json.load(f)

        self.get_commands(data, commands)
        return commands

    def _get_strategic_failure(self, response):
        response_text = response.get('value')
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

    def filter_and_remove_heredoc(self, commands):
        filtered_commands = []
        for command in commands:
            # Remove the <<< and everything after it
            filtered_command = re.sub(r' <<<.*', '', command)
            filtered_commands.append(filtered_command)
        return filtered_commands

    def _get_repeating_commands(self, commands):
        command_count = {}  # Dictionary to count occurrences of each command
        repeating_commands = []  # List to store commands that repeat exactly 3 times

        # Count the occurrences of each command, strip spaces to avoid hidden characters affecting counts
        for command in commands:
            command = command.strip()  # Remove any extra whitespace or newlines
            if command in command_count:
                command_count[command] += 1
            else:
                command_count[command] = 1

        # Add to repeating_commands if the command repeats exactly 3 times
        for command, count in command_count.items():
            if count >= 3:
                repeating_commands.append(command)

        return repeating_commands


    def analyze_interaction(self, model_responses):
        # Analyzing a single interaction for confusion
        commands = self.extract_commands('agent_data.json')
        filtered_commands = self.filter_and_remove_heredoc(commands)

        for response in model_responses:
            strategic_failure = self._get_strategic_failure(response)
            if self._get_strategic_failure(response) != None:
                failure_instance = Failure(
                    type = FailureType.STRATEGIC.value,
                    message = "Agent exhibited confusion",
                    command = "N/A",
                    context = {'response': strategic_failure}
                )

                if (failure_instance != None):
                    _print_failure(failure_instance)
                    print("\n")

        repeated_commands = self._get_repeating_commands(filtered_commands)
        if repeated_commands:
            for repeated_command in repeated_commands:
                failure_instance = Failure(
                    type = FailureType.LOOP.value,
                    message = "Agent used repetitive commands",
                    command = repeated_command,
                    context = "N/A"
                )

                if (failure_instance != None):
                    _print_failure(failure_instance)
                    print("\n")
        return None

    def store_responses(self, model_responses):
        with open('model_responses.txt', 'a') as file: 
            for response in model_responses: 
                file.write(str(response) + "\n\n")

def main():
    detector = AgentFailureDetector()
    model_responses = detector.extract_model_responses('agent_data.json')

    failure = detector.analyze_interaction(model_responses)
    if (failure != None):
            _print_failure(failure)
            print("\n")

    """for response in model_responses:
        failure = detector.analyze_interaction(response)
        if (failure != None):
            _print_failure(failure)
            print("\n")"""


main()


