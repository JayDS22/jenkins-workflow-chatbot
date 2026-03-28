"""
Troubleshoot Agent - the showstopper feature of this PoC.

This agent gets real build logs and error lines injected into its prompt.
When someone asks "why did my build fail?", it doesn't give generic advice
like "check your Jenkinsfile syntax". It reads the actual console output,
finds the actual error, and tells you the actual fix.

The prompt structure (Root Cause > Evidence > Fix > Prevention) mirrors
how senior engineers debug production issues. I used this exact pattern
when debugging CI/CD failures across 200+ Airflow DAGs at Bridgestone -
always start with what the logs actually say, not what you think might
be wrong.

The key insight: LLMs are surprisingly good at log analysis when you
give them the right context. The trick is extracting the relevant lines
first (the JenkinsContext.get_build_log does this) so the LLM isn't
drowning in 50,000 lines of Maven dependency resolution output.
"""

from langchain_groq import ChatGroq
from langchain.prompts import ChatPromptTemplate
from dotenv import load_dotenv
import logging

load_dotenv()

logger = logging.getLogger(__name__)

# Slightly higher temperature than the router - we want some creativity
# in the suggested fixes, but not so much that it hallucinates solutions
llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.1)

TROUBLESHOOT_PROMPT = ChatPromptTemplate.from_template("""
You are an expert Jenkins troubleshooting assistant. A user has a build failure or error and needs your help diagnosing it.

You have access to REAL data from their Jenkins instance (not hypothetical):

**Build Information:**
{build_info}

**Error Lines Extracted from Console Log:**
{error_lines}

**Console Log (tail section):**
{console_tail}

**Installed Plugins:**
{plugins}

**User's Question:**
{query}

Provide a structured response:

1. **Root Cause**: What is most likely causing this failure based on the actual log data you can see above. Be specific - reference the exact error.

2. **Evidence**: Quote the specific log lines that point to this diagnosis. Show the user exactly what you found.

3. **Fix**: Step-by-step instructions to resolve the issue. Be specific to their Jenkins setup - reference actual job names, plugin versions, and paths where relevant.

4. **Prevention**: How to prevent this from happening again. Pipeline best practices, plugin updates, or configuration changes that would catch this earlier.

Important: You have real data. Use it. Do not give generic advice like "check your configuration". Point to the specific error and the specific fix. If the log data is empty or missing, say so honestly.
""")

troubleshoot_chain = TROUBLESHOOT_PROMPT | llm


def troubleshoot(query: str, build_data: dict, plugins: list) -> str:
    """
    Analyze a build failure using real log data and error lines.

    Args:
        query: The user's question (e.g., "why did my build fail?")
        build_data: Output from JenkinsContext.get_build_log() - contains
                    console tail, error lines, build metadata
        plugins: List of installed plugin short names for compatibility context

    Returns:
        Structured diagnosis with root cause, evidence, fix, and prevention steps.
    """
    try:
        # Build a concise summary line so the LLM knows the basics upfront
        build_summary = (
            f"Job: {build_data.get('job_name', 'unknown')}, "
            f"Build #{build_data.get('build_number', '?')}, "
            f"Result: {build_data.get('result', 'unknown')}, "
            f"Duration: {build_data.get('duration_ms', 0)}ms"
        )

        error_lines = build_data.get("error_lines", [])
        error_text = "\n".join(error_lines) if error_lines else "No error lines extracted from the log."

        console_tail = build_data.get("console_tail", "No console output available.")

        # Cap plugin list at 50 to keep the prompt reasonable
        # Most Jenkins instances have 100+ plugins and listing all of them
        # just wastes tokens without adding useful context
        plugin_text = ", ".join(plugins[:50]) if plugins else "No plugin data available."

        result = troubleshoot_chain.invoke({
            "query": query,
            "build_info": build_summary,
            "error_lines": error_text,
            "console_tail": console_tail,
            "plugins": plugin_text,
        })
        return result.content

    except Exception as e:
        logger.error(f"Troubleshoot agent failed: {e}")
        return (
            f"I hit an error trying to analyze the build: {str(e)}\n\n"
            "This usually means the Groq API is rate-limited or the build data "
            "couldn't be parsed. Try again in a moment, or check that your "
            "GROQ_API_KEY is valid in the .env file."
        )
