import threading

class LLMStats:
    def __init__(self):
        self.lock = threading.Lock()
        self.regex_success = 0
        self.regex_failure = 0
        self.llm_calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_latency = 0.0

    def add_regex_success(self):
        with self.lock:
            self.regex_success += 1

    def add_regex_failure(self):
        with self.lock:
            self.regex_failure += 1

    def add_llm_call(self, prompt, comp, lat):
        with self.lock:
            self.llm_calls += 1
            self.prompt_tokens += prompt
            self.completion_tokens += comp
            self.total_latency += lat

    def print_cumulative(self):
        with self.lock:
            print(f"Regex Success : {self.regex_success}")
            print(f"Regex Failure : {self.regex_failure}")
            print(f"LLM Calls : {self.llm_calls}")
            print(f"Prompt Tokens : {self.prompt_tokens:,}")
            print(f"Completion Tokens : {self.completion_tokens:,}")
            print()

global_stats = LLMStats()
