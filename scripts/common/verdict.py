"""Parse TreasurAI free-text reasoning into a structured verdict label.

The model is instructed to classify each anomaly as one of:
  - anomali valid        -> 'valid'
  - false positive       -> 'false_positive'
  - perlu review manual  -> 'manual_review'

Returns 'unclear' when no recognizable verdict phrase is present.
"""

VERDICTS = ("valid", "false_positive", "manual_review", "unclear")


def parse_verdict(text: str) -> str:
    """Map a reasoning string to one of VERDICTS.

    Order matters: 'false positive' contains no other token, but a text may
    mention 'valid' while concluding 'false positive', so the negative verdict
    is checked first.
    """
    if not text:
        return "unclear"
    t = text.lower()
    if "false positive" in t or "false-positive" in t:
        return "false_positive"
    if "review manual" in t or "perlu review" in t or "tinjau manual" in t or "manual review" in t:
        return "manual_review"
    if "valid" in t:
        return "valid"
    return "unclear"
