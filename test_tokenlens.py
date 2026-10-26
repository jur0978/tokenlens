"""tokenlens —— 自检测试。

估算文本编码后的 token 数，按段落给出占用并指出可替换的高耗词。
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tokenlens  # noqa: E402


class TestTokenLens(unittest.TestCase):
    def test_cjk_costs_more_than_latin(self):
        cn = tokenlens.weight_of("这是一段中文文本")
        en = tokenlens.weight_of("this is english")
        self.assertGreater(cn, en)

    def test_estimate_is_positive(self):
        self.assertGreater(tokenlens.weight_of("任何文本"), 0)

    def test_empty_text(self):
        self.assertEqual(tokenlens.weight_of(""), 0)

    def test_wasteful_phrases_are_found(self):
        w = tokenlens.find_wasteful("为了能够进行操作")
        self.assertTrue(w)
        self.assertGreater(w[0]["chars_saved"], 0)

    def test_clean_text_has_no_waste(self):
        self.assertEqual(tokenlens.find_wasteful("今天写代码。"), [])

    def test_budget_over_is_flagged(self):
        r = tokenlens.weigh("这是一段比较长的中文文本。" * 100, 10)
        self.assertTrue(r["over_budget"])

    def test_paragraphs_are_split(self):
        r = tokenlens.weigh("第一段。\n\n第二段。", 1000)
        self.assertEqual(len(r["paragraphs"]), 2)
