"""
Intent Router - classifies incoming queries to the right specialist agent.

This is the same pattern I built at Aya Healthcare where we had 5+
specialized agents (screening, skill assessment, job matching, scheduling, FAQ)
and a router that figured out which one should handle each message.
That system supported 2000+ concurrent users with P95 <180ms.

For Jenkins, the classification is simpler - four intents:
  TROUBLESHOOT: something broke, user needs diagnosis
  WORKFLOW: user wants to learn how to do something
  RECOMMEND: user wants plugin or tool suggestions
  GENERAL: everything else (version info, general Jenkins knowledge)

The LLM does the classification because regex/keyword matching fails
on natural language. "My pipeline is slow" could be troubleshooting
OR a recommendation request depending on context.
"""

from langchain_groq import ChatGroq
from langchain.prompts import ChatPromptTemplate
from dotenv import load_dotenv
import logging

load_dotenv()

logger = logging.getLogger(__name__)

# Using temperature=0 for classification because we want deterministic routing.
# You don't want the same query randomly going to different agents.
llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

ROUTER_PROMPT = ChatPromptTemplate.from_template("""
You are an intent classifier for a Jenkins AI assistant. Classify the user's query into exactly one category.

Categories:
- TROUBLESHOOT: Build failures, errors, something not working, crashes, logs showing problems. The user needs diagnosis and a fix.
- WORKFLOW: The user wants to know HOW to do something. Setup, configuration, pipeline creation, migration, best practices.
- RECOMMEND: The user is asking which plugin to use, comparing tools or approaches, or wants suggestions for their Jenkins setup.
- GENERAL: General Jenkins questions, version info, architecture questions, or anything that doesn't fit the above.

User query: {query}

Jenkins context (if available): {context}

Respond with ONLY the category name in uppercase. Nothing else.
""")

router_chain = ROUTER_PROMPT | llm


def classify_intent(query: str, context: str = "") -> str:
    """
    Classify a user query into one of four intent categories.

    Returns one of: TROUBLESHOOT, WORKFLOW, RECOMMEND, GENERAL
    Falls back to GENERAL if the LLM returns something unexpected,
    which shouldn't happen with Llama 3 70B but defensive coding never hurts.
    """
    try:
        result = router_chain.invoke({"query": query, "context": context})
        category = result.content.strip().upper()

        valid_intents = ["TROUBLESHOOT", "WORKFLOW", "RECOMMEND", "GENERAL"]
        if category not in valid_intents:
            # Sometimes the model adds a period or extra text
            # Try to extract just the intent word
            for intent in valid_intents:
                if intent in category:
                    return intent
            logger.warning(f"Router returned unexpected category: '{category}', falling back to GENERAL")
            return "GENERAL"

        return category
    except Exception as e:
        logger.error(f"Router classification failed: {e}")
        return "GENERAL"
