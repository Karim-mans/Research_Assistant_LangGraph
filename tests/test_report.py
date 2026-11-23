import unittest
from unittest.mock import patch

with patch.dict("os.environ", {"OPENAI_API_KEY": "offline-test-key"}):
    from langgraph_research_agent.utils.nodes import finalise_report


class FinaliseReportTests(unittest.TestCase):
    def test_moves_source_after_conclusion_and_preserves_full_url(self):
        source = "[1] https://example.org/insights"
        result = finalise_report({
            "introduction": "# Transit",
            "content": f"## Insights\n\nRidership grew [1].\n\n## Sources\n{source}",
            "conclusion": "## Conclusion\nMore frequent service helped.",
        })

        parts = result["final_report"].split("\n\n---\n\n")
        self.assertEqual([part.strip() for part in parts], [
            "# Transit",
            "Ridership grew [1].",
            f"## Conclusion\nMore frequent service helped.\n\n## Sources\n{source}",
        ])

    def test_preserves_a_longer_heading_and_body_without_sources(self):
        content = "## Insights from interviews\n\nNew insights"
        result = finalise_report({
            "introduction": "Introduction",
            "content": content,
            "conclusion": "Conclusion",
        })

        self.assertEqual(
            result["final_report"],
            f"Introduction\n\n---\n\n{content}\n\n---\n\nConclusion",
        )
