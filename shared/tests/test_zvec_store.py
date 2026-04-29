from __future__ import annotations

import unittest

from shared.storage.zvec_store import _document_text


class DocumentTextTests(unittest.TestCase):
    def test_combines_dense_and_lexical_fields(self) -> None:
        doc = {
            "title": "Agentic Search Systems",
            "abstract": "Studies hybrid retrieval for agent evaluation.",
            "authors": ["Ada Lovelace", "Alan Turing"],
            "categories": ["cs.AI", "cs.IR"],
            "summary": "Combines vector search with keyword ranking.",
        }

        text = _document_text(doc, "title")

        self.assertIn("Agentic Search Systems", text)
        self.assertIn("hybrid retrieval", text)
        self.assertIn("Ada Lovelace", text)
        self.assertIn("cs.IR", text)


if __name__ == "__main__":
    unittest.main()
