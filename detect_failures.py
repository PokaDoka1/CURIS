from inspect import ClassFoundException
import json
import re
from difflib import SequenceMatcher
import openai

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
    command_history = []

    # _get_model_responses searches the dictionary to get all the model_responses
    # this function utilizes recursion
    def _get_model_responses(self, data, responses):
        if isinstance(data, dict):
            for key, value in data.items():
                if key == "model_response":
                    responses.append(value)
                elif isinstance(value, (dict, list)):
                    self._get_model_responses(value, responses)
        elif isinstance(data, list):
            for item in data:
                self._get_model_responses(item, responses)

        return responses

    # _get_commands searches the dictionary to get all of the commands
    # this function utilizes recursion
    def _get_commands(self, data, commands):
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
                    self._get_commands(value, commands)

        elif isinstance(data, list):
            for item in data:
                self._get_commands(item, commands)

        return commands

    # this function calls _get_model_responses to gather all the model_responses into an array
    def _extract_model_responses(self, json_file):
        model_responses = []
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        self._get_model_responses(data, model_responses)
        return model_responses

    # this function calls _get_commands to gather all the commands into an array
    def _extract_commands(self, json_file):
        commands = []
        with open(json_file, 'r') as f:
            data = json.load(f)

        self._get_commands(data, commands)
        return commands

    # _get_strategic_failure looks for specific key words in the model responses and returns any model_response
    # that has a strategic failure
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

    # _get_execution_failure looks for key words that indicate execution errors and returns the model_response
    # that contains that error
    def _get_execution_failure(self, response):
        response_text = response.get('value')
        response_text_lower = response_text.lower()

        execution_indicators = [
            "syntaxError",
            "unexpected token",
            "invalid syntax",
            "unterminated string",
            "missing parentheses",
            "unexpected EOF"
        ]

        for indicator in execution_indicators:
            if indicator in response_text_lower:
                return response_text
        return None

    # _filter_and_remove_heredoc removes the <<< from the agent's commands
    # helper functionto get_repeating_commands
    def _filter_and_remove_heredoc(self, commands):
        filtered_commands = []
        for command in commands:
            # Remove the <<< and everything after it
            filtered_command = re.sub(r' <<<.*', '', command)
            filtered_commands.append(filtered_command)
        return filtered_commands

    # _get_repeating_commands returns an array of  all the commands that the agent has repeated 3 or more times
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

    # Sequence Matcher code I wasn't able to test
    """def _get_repeating_commands(self, commands):
        repeating_commands = []
        history = self.command_history[task_id]
        history.append(command)
        
        if len(history) >= 3:
            # Check for exact repetition
            if len(set(history[-3:])) == 1:
                return True
            
            # Check for similar commands using string similarity
            similarity_threshold = 0.8
            last_commands = history[-3:]
            similarities = [
                SequenceMatcher(None, last_commands[i], last_commands[i+1]).ratio()
                for i in range(len(last_commands)-1)
            ]
            return all(sim > similarity_threshold for sim in similarities)
            
        return False"""

    # analyze_interactoin checks for every different failure type, and prints all the failures it finds from the logged data
    def analyze_interaction(self, model_responses):
        failures = []
        # Analyzing a single interaction for confusion
        commands = self._extract_commands('agent_data.json')
        filtered_commands = self._filter_and_remove_heredoc(commands)

        for response in model_responses:
            execution_error = self._get_execution_failure(response)
            if execution_error != None:
                failure_instance = Failure(
                    type = FailureType.EXECUTION.value,
                    message = "Agent exhibited execution errors",
                    command = "N/A",
                    context = {'response': execution_error}
                )

                if (failure_instance != None):
                    failures.append(failure_instance)
                    _print_failure(failure_instance)
                    print("\n")

        for response in model_responses:
            strategic_failure = self._get_strategic_failure(response)
            if strategic_failure != None:
                failure_instance = Failure(
                    type = FailureType.STRATEGIC.value,
                    message = "Agent exhibited confusion",
                    command = "N/A",
                    context = {'response': strategic_failure}
                )

                if (failure_instance != None):
                    failures.append(failure_instance)
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
                    failures.append(failure_instance)
                    _print_failure(failure_instance)
                    print("\n")
        return None
        
    # populate the model_responses.txt file with the agent's model responses to better aid with debugging
    def _store_responses(self, model_responses):
        with open('model_responses.txt', 'a') as file: 
            for response in model_responses: 
                file.write(str(response) + "\n\n")

# I was not able to test this yet              
class decorator():
    def get_new_command_from_llm(failure):
        # Prepare the prompt with failure details
        prompt = f"""
        The following is an agent failure context:
        
        Failure Type: {failure.type}
        Failure Message: {failure.message}
        Command: {failure.command}
        Context: {failure.context}
        
        Given this information, please suggest a new command or strategy that might solve the issue for the agent.
        Only respond with a command the agent should now try. Only a command."""
        
        
        # Send the prompt to the LLM for a response
        response = openai.Completion.create(
            model="gpt-3.5-turbo",  # Example model
            prompt=prompt,
            max_tokens=150,  # Limit the response size
            temperature=0.7  # Control creativity
        )

        # Extract the response text and return it
        new_command = response.choices[0].text.strip()
        return new_command

def main():
    detector = AgentFailureDetector()
    model_responses = detector._extract_model_responses('agent_data.json')

    detector.analyze_interaction(model_responses)


main()


