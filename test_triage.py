from arxiv_worker.paper_analyzer import _parse_triage_lines
from shared.config import Settings
import logging

logging.basicConfig(level=logging.DEBUG)

def test():
    content = "2604.25917|high\n2604.25847|high"
    expected = {"2604.25917v1", "2604.25847v1"}
    print(_parse_triage_lines(content, expected))

if __name__ == "__main__":
    test()