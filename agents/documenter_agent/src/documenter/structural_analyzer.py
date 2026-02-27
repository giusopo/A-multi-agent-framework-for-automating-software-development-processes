import re


def analyze_sequence_structural(uml_code: str) -> str:
    """
    Analisi strutturale deterministica del diagramma di sequenza.
    Non usa LLM.
    Restituisce feedback testuale.
    """

    if not uml_code:
        return "Empty UML code."

    feedback = []

    # Normalizza testo
    lower_code = uml_code.lower()

    # ============================
    # 🔹 Regola 1: presenza attore User
    # ============================

    # Match robusto: actor "User" oppure actor User
    user_actor_pattern = r'actor\s+"?user"?'

    if not re.search(user_actor_pattern, lower_code):
        feedback.append("Missing main actor 'User'. Add actor User at start.")

    # ============================
    # 🔹 Regola 2: almeno un participant
    # ============================

    if not re.search(r'\bparticipant\b', lower_code):
        feedback.append("No participants defined.")

    # ============================
    # 🔹 Regola 3: almeno un messaggio
    # ============================

    if not re.search(r'\-\>', lower_code):
        feedback.append("No message interactions defined.")

    # ============================

    if not feedback:
        return "Structure OK."

    return "\n".join(feedback)