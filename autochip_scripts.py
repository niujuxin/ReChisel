import os
import re

class Conversation:
    def __init__(self, log_file=None):
        self.messages = []
        self.log_file = log_file

        if self.log_file and os.path.exists(self.log_file):
            open(self.log_file, 'w').close()

    def add_message(self, role, content):
        """Add a new message to the conversation."""
        self.messages.append({'role': role, 'content': content})

        if self.log_file:
            with open(self.log_file, 'a') as file:
                file.write(f"{role}: {content}\n")

    def get_messages(self):
        """Retrieve the entire conversation."""
        return self.messages

    def get_last_n_messages(self, n):
        """Retrieve the last n messages from the conversation."""
        return self.messages[-n:]

    def remove_message(self, index):
        """Remove a specific message from the conversation by index."""
        if index < len(self.messages):
            del self.messages[index]

    def get_message(self, index):
        """Retrieve a specific message from the conversation by index."""
        return self.messages[index] if index < len(self.messages) else None

    def clear_messages(self):
        """Clear all messages from the conversation."""
        self.messages = []

    def __str__(self):
        """Return the conversation in a string format."""
        return "\n".join([f"{msg['role']}: {msg['content']}" for msg in self.messages])



def find_verilog_modules(markdown_string):
    module_pattern1 = r'\bmodule\b\s+\w+\s*\([^)]*\)\s*;.*?endmodule\b'
    module_pattern2 = r'\bmodule\b\s+\w+\s*#\s*\([^)]*\)\s*\([^)]*\)\s*;.*?endmodule\b'
    module_matches1 = re.findall(module_pattern1, markdown_string, re.DOTALL)
    module_matches2 = re.findall(module_pattern2, markdown_string, re.DOTALL)
    module_matches = module_matches1 + module_matches2
    return module_matches if module_matches else []


def write_code_blocks_to_file(markdown_string, filename):
    code_match = find_verilog_modules(markdown_string)
    if not code_match:
        raise RuntimeError('No code blocks found in markdown file')
    code = "\n".join(code_match)
    with open(filename, 'w') as file:
        file.write(code)


def parse_iverilog_output(output):
    # Regular expression to match the errors and warnings from the output
    pattern = re.compile(r'^(.*\.v):(\d+): (error|warning): (.*)$', re.MULTILINE)
    results = []
    for match in pattern.findall(output):
        file_name, line_number, _, message = match
        line_number = int(line_number)
        # Extract the associated line from the file
        with open(file_name, 'r') as file:
            lines = file.readlines()
            if 1 <= line_number <= len(lines):
                associated_line = lines[line_number - 1].strip()  # -1 because list index starts from 0
            else:
                associated_line = "Unable to extract line. Line number may be out of range."
        results.append({
            'file_name': file_name,
            'line_number': line_number,
            'message': message,
            'associated_line': associated_line
        })
    return results
