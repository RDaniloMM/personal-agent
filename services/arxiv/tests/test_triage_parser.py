from __future__ import annotations

import unittest

from arxiv_worker.paper_analyzer import _parse_triage_response


class ParseTriageResponseTests(unittest.TestCase):
    def test_accepts_line_based_triage_output(self) -> None:
        papers = [
            {"arxiv_id": "2604.12345v1"},
            {"arxiv_id": "2604.12346v1"},
        ]

        parsed = _parse_triage_response(
            "2604.12345v1|high\n2604.12346v1|medium",
            papers,
        )

        self.assertEqual(
            parsed,
            [
                {"arxiv_id": "2604.12345v1", "relevance": "high"},
                {"arxiv_id": "2604.12346v1", "relevance": "medium"},
            ],
        )

    def test_defaults_missing_items_to_medium(self) -> None:
        papers = [
            {"arxiv_id": "2604.12345v1"},
            {"arxiv_id": "2604.12346v1"},
        ]

        parsed = _parse_triage_response(
            '{"papers":[{"arxiv_id":"2604.12345v1","relevance":"low"}]}',
            papers,
        )

        self.assertEqual(
            parsed,
            [
                {"arxiv_id": "2604.12345v1", "relevance": "low"},
                {"arxiv_id": "2604.12346v1", "relevance": "medium"},
            ],
        )


if __name__ == "__main__":
    unittest.main()
