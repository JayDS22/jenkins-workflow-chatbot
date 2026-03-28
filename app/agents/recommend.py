"""
Recommend Agent - plugin and tooling recommendations with compatibility awareness.

Jenkins has 1800+ plugins. Picking the right one is genuinely hard, especially
when you need to think about compatibility with your existing setup.

This agent cross-references what you're asking for against what you already
have installed. It won't recommend the Docker Pipeline plugin if you already
have it. It will warn you if a plugin has known conflicts with something
in your stack.

The recommendation structure (top pick, alternatives, compatibility, install steps)
is intentional. It mirrors how a senior Jenkins admin would answer the question:
"I'd go with X because of Y, but Z is also good if you need W."
"""

from langchain_groq import ChatGroq
from langchain.prompts import ChatPromptTemplate
from dotenv import load_dotenv
import logging

load_dotenv()

logger = logging.getLogger(__name__)

llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.2)

RECOMMEND_PROMPT = ChatPromptTemplate.from_template("""
You are a Jenkins plugin and tooling advisor. The user needs a recommendation.

Their current Jenkins setup (real data from their instance):
- Jenkins version: {jenkins_version}
- Already installed plugins: {plugins}
- Existing jobs: {jobs}

**User's Question:**
{query}

Provide:

1. **Recommendation**: Your top pick with clear reasoning. If they already have a plugin that does what they're asking about, tell them - don't recommend something redundant.

2. **Alternatives**: 1-2 alternatives and when you'd pick them instead. Be honest about tradeoffs.

3. **Compatibility note**: Check their Jenkins version and existing plugins. Flag any known conflicts or version requirements. If everything looks compatible, say so.

4. **Installation**: Exact steps to install and configure it. Include the plugin's short name for CLI installation (e.g., `jenkins-plugin-cli --plugins docker-workflow`).

Only recommend plugins that actually exist in the Jenkins ecosystem. Do not invent plugin names. If you're not sure a plugin exists, say so rather than making one up.
""")

recommend_chain = RECOMMEND_PROMPT | llm


def recommend(query: str, server_info: dict) -> str:
    """
    Generate context-aware plugin/tool recommendations.

    Cross-references the user's installed plugins so we don't suggest
    things they already have, and can flag compatibility issues with
    their current setup.

    Args:
        query: What the user is looking for (e.g., "Slack notifications plugin")
        server_info: Output from JenkinsContext.get_server_info()

    Returns:
        Structured recommendation with alternatives and compatibility notes.
    """
    try:
        plugins = server_info.get("installed_plugins", [])
        jobs = server_info.get("jobs", [])

        result = recommend_chain.invoke({
            "query": query,
            "jenkins_version": server_info.get("jenkins_version", "unknown"),
            "plugins": ", ".join(plugins[:50]) if plugins else "No plugin data available",
            "jobs": ", ".join(jobs) if jobs else "No existing jobs",
        })
        return result.content

    except Exception as e:
        logger.error(f"Recommend agent failed: {e}")
        return (
            f"Hit an error generating the recommendation: {str(e)}\n\n"
            "This is usually a Groq API rate limit. Give it a moment and retry."
        )
