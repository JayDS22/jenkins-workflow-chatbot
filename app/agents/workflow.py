"""
Workflow Agent - gives step-by-step Jenkins guidance that's actually relevant.

The problem with generic Jenkins documentation is that it assumes a clean slate.
Real Jenkins instances have existing plugins, existing jobs, and existing
configurations. This agent knows about all of that.

When someone asks "how do I set up a multibranch pipeline?", a generic
chatbot gives the same answer every time. This one checks if you already
have the git plugin, already have GitHub integration, and already have
similar jobs - then customizes the guidance to your actual setup.

This is the "Guide User Workflow" part of the GSoC project name.
Not just answering questions, but walking users through tasks with
awareness of where they're starting from.
"""

from langchain_groq import ChatGroq
from langchain.prompts import ChatPromptTemplate
from dotenv import load_dotenv
import logging

load_dotenv()

logger = logging.getLogger(__name__)

# Temperature 0.2 - we want helpful, slightly creative responses
# but the steps need to be technically accurate
llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.2)

WORKFLOW_PROMPT = ChatPromptTemplate.from_template("""
You are a Jenkins workflow guide. The user wants to accomplish something in Jenkins and needs practical, step-by-step help.

You know the following about their ACTUAL Jenkins instance (this is real data, not hypothetical):
- Jenkins version: {jenkins_version}
- Installed plugins: {plugins}
- Existing jobs: {jobs}

**User's Question:**
{query}

Provide a response with:

1. **What you'll need**: List any plugins they need. IMPORTANT - check the installed plugins list above first. If they already have a required plugin, say "You already have [plugin] installed." If they're missing one, tell them to install it and give the exact plugin name.

2. **Step-by-step guide**: Numbered steps specific to their Jenkins version and setup. If they already have similar jobs configured, reference those as starting points.

3. **Example Jenkinsfile** (if applicable): A working pipeline script they can copy-paste. Keep it practical and tested - not a toy example.

4. **Common pitfalls**: Things that typically go wrong with this workflow. Draw from real-world experience - version incompatibilities, permission issues, credential scoping mistakes.

Be practical. Don't explain what Jenkins is. They're already using it. Jump straight to the answer.
""")

workflow_chain = WORKFLOW_PROMPT | llm


def guide_workflow(query: str, server_info: dict) -> str:
    """
    Generate context-aware workflow guidance.

    The server_info dict contains the live Jenkins state so the agent
    can tailor its response. If Jenkins is offline, it'll still work
    with mock data but the advice won't be personalized.

    Args:
        query: What the user wants to do (e.g., "set up multibranch pipeline")
        server_info: Output from JenkinsContext.get_server_info()

    Returns:
        Step-by-step guidance customized to the user's Jenkins setup.
    """
    try:
        plugins = server_info.get("installed_plugins", [])
        jobs = server_info.get("jobs", [])

        result = workflow_chain.invoke({
            "query": query,
            "jenkins_version": server_info.get("jenkins_version", "unknown"),
            "plugins": ", ".join(plugins[:50]) if plugins else "No plugin data available",
            "jobs": ", ".join(jobs) if jobs else "No existing jobs",
        })
        return result.content

    except Exception as e:
        logger.error(f"Workflow agent failed: {e}")
        return (
            f"I ran into an issue generating the workflow guide: {str(e)}\n\n"
            "Check that your GROQ_API_KEY is set correctly in the .env file. "
            "The free tier has rate limits, so if you've been making a lot of "
            "requests, wait a minute and try again."
        )
