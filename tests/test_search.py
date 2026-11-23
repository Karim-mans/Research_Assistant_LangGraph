import unittest
from unittest.mock import patch

with patch.dict("os.environ", {"OPENAI_API_KEY": "offline-test-key"}):
    from langgraph_research_agent.utils import nodes
    from langgraph_research_agent.utils.objects import SearchQuery


class TavilySearchTests(unittest.TestCase):
    def setUp(self):
        llm = self.enterContext(patch.object(nodes, "llm"))
        llm.with_structured_output.return_value.invoke.return_value = SearchQuery(
            search_query="bus frequency"
        )
        self.search = self.enterContext(patch.object(nodes, "TavilySearch")).return_value

    def test_both_nodes_propagate_the_original_provider_exception(self):
        error = ValueError("Error 429: search quota exceeded")
        self.search.invoke.return_value = {"error": error}
        for node in (nodes.search_web, nodes.search_web2):
            with self.subTest(node=node.__name__):
                with self.assertRaises(ValueError) as caught:
                    node({"messages": []})
                self.assertIs(caught.exception, error)

    def test_text_error_reaches_the_caller(self):
        self.search.invoke.return_value = {"error": "invalid API key"}
        with self.assertRaisesRegex(RuntimeError, "Tavily search failed: invalid API key"):
            nodes.search_web({"messages": []})

    def test_missing_results_are_reported(self):
        self.search.invoke.return_value = {"query": "bus frequency"}
        with self.assertRaisesRegex(ValueError, "results list"):
            nodes.search_web({"messages": []})

    def test_both_nodes_still_search_and_return_source_context(self):
        self.search.invoke.return_value = {
            "results": [{"url": "https://example.org/transit", "content": "More frequent service."}]
        }
        for node in (nodes.search_web, nodes.search_web2):
            with self.subTest(node=node.__name__):
                result = node({"messages": []})
                self.search.invoke.assert_called_with({"query": "bus frequency"})
                self.assertEqual(len(result["context"]), 1)
                self.assertIn("https://example.org/transit", result["context"][0])
                self.assertIn("More frequent service.", result["context"][0])
        self.assertEqual(self.search.invoke.call_count, 2)
