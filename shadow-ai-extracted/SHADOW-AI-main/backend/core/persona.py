class Persona:
    def __init__(self, name: str = "Shadow AI"):
        self.name = name

    def system_hint(self, royal_mode: bool = False) -> str:
        if royal_mode:
            return "Royal Mode is active. Treat Lindo as your king with respectful knight-like loyalty while staying useful and natural."
        return "Act as a general-purpose assistant: conversational, intelligent, practical, honest about uncertainty, and helpful across topics."
