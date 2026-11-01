"""Замороженный набор: агент не меняет эти тесты в том же акте, где правит код."""
import unittest

from src.app import greet


class TestGreet(unittest.TestCase):
    def test_greet(self):
        self.assertEqual(greet("мир"), "привет, мир")
