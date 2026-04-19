"""
Central prompt registry — all LLM prompt strings defined here.
Import from this module instead of defining prompt strings inline.
"""
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

CHAT_SYSTEM = "You are a helpful AI assistant."

CLASSIFY_SYSTEM = (
    "You are a message router. Classify the user message as either AGENT or CHAT.\n"
    "Reply with exactly one word: AGENT or CHAT.\n\n"
    "AGENT — the message requires multi-step autonomous work that cannot be answered "
    "in one pass: internet research, writing & executing code, creating a structured plan "
    "across multiple steps, or running tests.\n"
    "CHAT — everything else: questions about specific documents or data the user provides, "
    "simple factual questions, greetings, explanations, summaries, translations, or any "
    "query that can be answered with a single LLM response.\n\n"
    "When in doubt, prefer CHAT."
)

TITLE_SYSTEM = (
    "You are a helpful assistant that generates short, concise titles for conversations. "
    "Max 6 words. No quotes. No prefixes like 'Title:'."
)


def titleUserPrompt(userMessage: str, aiResponse: str) -> str:
    return f"User: {userMessage[:500]}\nAI: {aiResponse[:500]}\n\nGenerate a title for this conversation:"


def docrefInstruction(sources: List[Dict]) -> str:
    """Build inline <docref> citation instruction appended to the system prompt."""
    if not sources:
        return ""
    seen: set = set()
    unique = []
    for s in sources:
        key = s.get("filename", "")
        if key and key not in seen:
            seen.add(key)
            unique.append(s)
    if not unique:
        return ""
    lines = []
    for s in unique:
        docId = s.get("documentId", "")
        filename = s.get("filename", "")
        entry = f'- file="{filename}"' + (f' docId="{docId}"' if docId else "")
        lines.append(entry)
    docList = "\n".join(lines)
    return (
        "\n\nWhen your answer references content from a document listed below, "
        "cite it inline using this XML tag:\n"
        '  <docref file="filename" docId="id" page="N">cited text</docref>\n'
        "Use page attribute only when you know the page number from the context. "
        "Available documents:\n"
        f"{docList}"
    )


# ---------------------------------------------------------------------------
# Memory — long-term fact extraction
# ---------------------------------------------------------------------------

FACT_EXTRACTION_SYSTEM = (
    "You extract durable personal facts about the user from conversations. "
    "Facts must be genuinely useful for future personalization "
    "(preferences, goals, background, constraints). "
    "Return a valid JSON array of strings. "
    "Return [] if nothing is worth remembering. "
    "Do not duplicate facts already in the existing list."
)


def factExtractionUserPrompt(userMsg: str, assistantMsg: str, existing: List[str]) -> str:
    existingStr = "\n".join(f"- {f}" for f in existing) if existing else "None"
    return (
        f"Existing facts:\n{existingStr}\n\n"
        f"User: {userMsg[:800]}\n"
        f"Assistant: {assistantMsg[:800]}\n\n"
        "Extract 0-3 new facts as a JSON array:"
    )


# ---------------------------------------------------------------------------
# Memory — short-term conversation summary
# ---------------------------------------------------------------------------

CONV_SUMMARY_SYSTEM = "You are a helpful assistant that summarizes conversations concisely."


def convSummaryUserPrompt(existingSummary: Optional[str], turnsText: str) -> str:
    if existingSummary:
        return (
            f"Previous summary:\n{existingSummary}\n\n"
            f"New conversation turns:\n{turnsText}\n\n"
            "Update the summary to incorporate the new turns. "
            "Keep it concise (3-5 sentences). Preserve key facts."
        )
    return (
        f"Conversation:\n{turnsText}\n\n"
        "Summarize the key points of this conversation in 3-5 sentences "
        "so the context can be continued in future turns."
    )


# ---------------------------------------------------------------------------
# Knowledge — document summary
# ---------------------------------------------------------------------------

DOCUMENT_SUMMARY_SYSTEM = "You are a helpful assistant that summarizes documents concisely."


def documentSummaryUserPrompt(text: str) -> str:
    return f"Summarize the following document in 3-5 sentences:\n\n{text}"


# ---------------------------------------------------------------------------
# Agents — supervisor
# ---------------------------------------------------------------------------

SUPERVISOR_SYSTEM = """You are the Supervisor of a multi-agent pipeline. Your only job is to decide which agent to run next.

Agents available:
- research: gather information, search web and knowledge base
- planner: create a structured execution plan from research
- implement: execute the plan, write code or documents
- testing: validate and test the implementation
- report: synthesize everything into a final report
- END: the task is complete, stop

Routing rules (use judgment, these are guidelines):
1. No research yet → research
2. Has research but no plan → planner
3. Has plan but no implementation → implement
4. Has implementation but no testing → testing
5. Testing passed → report
6. Testing failed AND iterationCount < maxIterations → implement (retry)
7. Testing failed AND iterationCount >= maxIterations → report (partial failure)
8. Has final report → END
9. status is failed/cancelled → END

Respond with EXACTLY one word: the agent name or END. Nothing else."""


def supervisorUserPrompt(stateContext: str) -> str:
    return f"Current pipeline state:\n{stateContext}\n\nWhich agent should run next?"


# ---------------------------------------------------------------------------
# Agents — task generation
# ---------------------------------------------------------------------------

TASK_GEN_PROMPT = (
    "You are a task planner for the {agentType} phase.\n"
    "Given the user's goal and conversation context, generate a concise list of specific tasks "
    "that need to be completed for this phase.\n\n"
    "Rules:\n"
    "- Generate 2-5 tasks maximum\n"
    "- Each task should be actionable and specific\n"
    "- Tasks should be ordered by execution sequence\n"
    "- Respond in pure JSON: {{\"tasks\": [{{\"description\": \"task description\"}}]}}"
)


# ---------------------------------------------------------------------------
# Agents — sub-agent system prompts
# ---------------------------------------------------------------------------

def plannerSystemPrompt(proceduralText: str, threadContext: str = "") -> str:
    prompt = (
        "You are a Planner Agent. Create a detailed, actionable plan. "
        "Use createPlan tool to produce a structured plan.\n\n"
        f"Successful planning patterns:\n{proceduralText}"
    )
    if threadContext:
        prompt += f"\n\nThread context:\n{threadContext}"
    return prompt


def researchSystemPrompt(episodicText: str, semanticText: str, threadContext: str = "") -> str:
    prompt = (
        "You are a Research Agent. Use available tools to search the web and "
        "internal knowledge base. Synthesize findings into clear, structured points.\n\n"
        f"Past research experience:\n{episodicText}\n\n"
        f"Relevant knowledge:\n{semanticText}"
    )
    if threadContext:
        prompt += f"\n\nThread context:\n{threadContext}"
    return prompt


def implementSystemPrompt(proceduralText: str, threadContext: str = "") -> str:
    prompt = (
        "You are an Implement Agent. Execute tasks by writing code or documents. "
        "Use codeWriter for code files, fileWriter for text/markdown, shellRunner to run commands.\n\n"
        f"Tech preferences:\n{proceduralText}"
    )
    if threadContext:
        prompt += f"\n\nThread context:\n{threadContext}"
    return prompt


def testingSystemPrompt(episodicText: str, threadContext: str = "") -> str:
    prompt = (
        "You are a Testing Agent. Validate the implementation against the goal. "
        "Use testCaseGenerator to create tests, testRunner to run them, "
        "validator to check outputs.\n\n"
        f"Common failure patterns:\n{episodicText}"
    )
    if threadContext:
        prompt += f"\n\nThread context:\n{threadContext}"
    return prompt


def reportSystemPrompt(proceduralText: str, threadContext: str = "") -> str:
    prompt = (
        "You are a Report Agent. Create a comprehensive report. "
        "Use reportWriter to produce a structured markdown report.\n\n"
        f"Report format preferences:\n{proceduralText}"
    )
    if threadContext:
        prompt += f"\n\nThread context:\n{threadContext}"
    return prompt


# ---------------------------------------------------------------------------
# Agents — memory
# ---------------------------------------------------------------------------

AGENT_FACT_EXTRACTION_SYSTEM = (
    "You are an expert fact extractor. Extract ONLY factual information from the user messages below. \n"
    "Focus strictly on these categories: preferences, personal details, plans, activities, health, professional, misc.\n"
    "If there are no facts worth remembering (e.g., greetings, generic statements, vague comments), DO NOT extract anything.\n"
    'Respond in pure JSON format: {"facts": ["fact 1", "fact 2", ...]} or {"facts": []} if nothing is found.'
)


def agentDedupPrompt(newFact: str, memoriesStr: str) -> str:
    return (
        f'You are coordinating memory deduplication.\n'
        f'New Fact: "{newFact}"\n'
        f'Existing Memories:\n{memoriesStr}\n\n'
        "Rules:\n"
        "- ADD: The fact is completely new and distinct from existing ones.\n"
        "- UPDATE: The fact overlaps heavily with an existing memory but contains new details. "
        "Provide the 'memoryId' to update, and the merged 'content'.\n"
        "- DELETE: The new fact completely contradicts an existing memory without replacing it cleanly, "
        "or the user explicitly asked to forget it. Provide 'memoryId'.\n"
        "- NONE: The exact same factual information is already present.\n\n"
        'Response must be pure JSON: {"action": "ADD|UPDATE|DELETE|NONE", '
        '"memoryId": "<string or null>", "content": "<merged content if UPDATE>"}'
    )


def conversationCompactionPrompt(existingCompact: str, newText: str) -> str:
    base = (
        "Summarize the following conversation messages into 2-3 concise sentences, "
        "preserving key user preferences, clarifications, and context.\n\n"
    )
    if existingCompact:
        base += f"Existing summary:\n{existingCompact}\n\n"
    return base + f"New messages:\n{newText}"


def taskHistoryCompactionPrompt(existingRunning: str, compactText: str) -> str:
    base = "Summarize the following completed agent tasks into 2-3 sentences of dense context.\n\n"
    if existingRunning:
        base += f"Existing summary:\n{existingRunning}\n\n"
    return base + f"Tasks to compact:\n{compactText}"
