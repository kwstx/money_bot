import pytest
from src.parser.normalizer import TextNormalizer

def test_normalize_whitespace():
    text = "This   has \t weird \n  spaces"
    assert TextNormalizer.normalize(text) == "This has weird spaces"

def test_normalize_unicode():
    # zero-width spaces
    text = "Hello\u200bWorld"
    assert TextNormalizer.normalize(text) == "HelloWorld"
    
def test_normalize_punctuation():
    text = "“Smart quotes” and ‘single quotes’ — dash"
    # The normalizer converts stylized to standard
    assert TextNormalizer.normalize(text) == '"Smart quotes" and \'single quotes\' - dash'

def test_empty_string():
    assert TextNormalizer.normalize(None) == ""
    assert TextNormalizer.normalize("") == ""
