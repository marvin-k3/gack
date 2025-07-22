import pytest
from gack import hello

def test_hello():
    assert hello() == "Hello from gack!"
