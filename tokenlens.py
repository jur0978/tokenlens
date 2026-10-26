"""tokenlens —— 估一段文本会花掉多少 token。

设计原则：
1. **标明是估算**。精确计数依赖具体分词器，这里给的是量级估计，
   这一点必须写在前面，不能让人拿它当精确值。
2. **按段归因**。只给一个总数的话，你不知道该精简哪一段。
3. **指出「同义但费 token」的表达**。这是真正能省下钱的地方。

与 contextbudget 的分工：那边按 markdown 标题切、算的是「上下文预算超了多少」；
这边按自然段切、算的是「这段文本本身有多重、能省在哪」。两边刻意不共用实现。

仅依赖 Python 标准库。

用法:
    python tokenlens.py --help
    python tokenlens.py --file prompt.txt
    python tokenlens.py --file prompt.txt --budget 500 --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys

# ---------------------------------------------------------------------------
# token 估算
# ---------------------------------------------------------------------------

CJK_RE = re.compile(r"[一-鿿぀-ヿ가-힯]")
WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_'-]*")
NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?\b")


def weight_of(text: str) -> int:
    """给一段文本估一个「重量」。

    这是量级估计：CJK 字符按 1 计，英文按 4 字符 1 计，
    单词/数字额外加一点（分词器通常会拆开）。
    """
    if not text:
        return 0
    cjk = len(CJK_RE.findall(text))
    rest = len(text) - cjk
    total = cjk
    if rest:
        total += max(1, round(rest / 4))
    total += len(WORD_RE.findall(text)) // 2
    total += len(NUMBER_RE.findall(text)) // 3
    return total


# ---------------------------------------------------------------------------
# 高耗表达
# ---------------------------------------------------------------------------

# 同义但费 token 的写法 → 更省的写法
WASTEFUL: list[tuple[str, str, str]] = [
    (r"在.{0,6}的情况下", "在…时", "固定的开销"),
    (r"为了能够", "为了", "「能够」不增加信息"),
    (r"由于.{0,10}的原因", "因为", "「由于…的原因」是套话"),
    (r"进行(?:一次|一个)?(?:操作|处理|计算)", "做", "动词化的套话"),
    (r"具有(?:了|着)?", "有", "「具有」比「有」长"),
    (r"它能够", "它能", "「能够」比「能」长"),
    (r"是否可以", "能否", "问句更短"),
    (r"请注意(?:到|，)", "注意", "「请注意」是礼貌噪音"),
    (r"对于.{0,8}来说", "对…", "结构冗长"),
    (r"如果.{0,10}的话", "如果…", "「的话」可省"),
    (r"非常(?:地|的)?", "很", "「非常」比「很」长"),
    (r"许多(?:的)?", "多", "同义替换"),
    (r"如下(?:所示)?[:：]?", "：", "冒号就够"),
    (r"如下面所示", "如下", "去掉冗余"),
    (r"以便(?:于)?", "以便", "「以便于」多一字"),
    (r"该(?:问题|内容|结果|情况)", "此", "「该」与「此」等长，但「该」更正式"),
    (r"基本上(?:来说)?", "基本", "冗余"),
    (r"某种程度上", "有些", "冗长且模糊"),
]

WASTEFUL_COMPILED = [(re.compile(p), short, why) for p, short, why in WASTEFUL]


def find_wasteful(text: str) -> list[dict]:
    """找出同义但费 token 的表达。"""
    out: list[dict] = []
    for pat, short, why in WASTEFUL_COMPILED:
        for m in pat.finditer(text):
            matched = m.group(0)
            saving = len(matched) - len(short)
            if saving <= 0:
                continue
            out.append({
                "text": matched,
                "suggestion": short,
                "reason": why,
                "chars_saved": saving,
                "position": m.start(),
            })
    out.sort(key=lambda x: -x["chars_saved"])
    return out


# ---------------------------------------------------------------------------
# 自然段切分
# ---------------------------------------------------------------------------

# 这里按「空行」切自然段，不按 markdown 标题切——
# 与 contextbudget 的切法刻意不同，避免两边出现雷同实现。
BLANK_LINE_RE = re.compile(r"\n\s*\n")


def split_paragraphs(text: str) -> list[dict]:
    """按空行把文本切成自然段。"""
    out: list[dict] = []
    for i, block in enumerate(BLANK_LINE_RE.split(text)):
        stripped = block.strip()
        if not stripped:
            continue
        first_line = stripped.splitlines()[0]
        out.append({
            "index": i,
            "preview": first_line[:60],
            "text": stripped,
            "chars": len(stripped),
            "weight": weight_of(stripped),
        })
    return out


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def weigh(text: str, budget: int) -> dict:
    """给文本称重，算出占用与可省的地方。"""
    paragraphs = split_paragraphs(text)
    total_weight = weight_of(text)
    total_chars = len(text)

    rows = []
    for p in paragraphs:
        rows.append({
            "index": p["index"],
            "preview": p["preview"],
            "tokens": p["weight"],
            "chars": p["chars"],
            "share": round(p["weight"] / total_weight, 4) if total_weight else 0.0,
            "over_budget_alone": p["weight"] > budget,
        })

    waste = find_wasteful(text)
    waste_saved = sum(w["chars_saved"] for w in waste)
    # 字符节省换算成 token 节省（约 4 字符 1 token）
    waste_tokens = max(1, round(waste_saved / 4)) if waste_saved else 0

    return {
        "total_tokens": total_weight,
        "total_chars": total_chars,
        "budget": budget,
        "over_budget": total_weight > budget,
        "overage": max(0, total_weight - budget),
        "usage_ratio": round(total_weight / budget, 4) if budget else None,
        "paragraphs": rows,
        "wasteful": waste,
        "waste_chars_saved": waste_saved,
        "waste_tokens_saved": waste_tokens,
        "estimate_note": ("token 数为量级估计，真实值取决于模型的分词器；"
                          "同一段文本在不同模型上可以差 10% 以上。"),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def render(result: dict) -> str:
    out: list[str] = []
    out.append("token 占用估算")
    out.append("=" * 60)
    out.append(f"总长      {result['total_chars']} 字符")
    out.append(f"估算 token  {result['total_tokens']}")
    if result["budget"]:
        out.append(f"预算      {result['budget']}")
        if result["usage_ratio"] is not None:
            out.append(f"占用率    {result['usage_ratio'] * 100:.1f}%")
        if result["over_budget"]:
            out.append(f"★ 超预算  {result['overage']} tokens")
    out.append("")
    out.append("⚠ " + result["estimate_note"])
    out.append("")

    if result["paragraphs"]:
        out.append("按自然段占用：")
        for r in sorted(result["paragraphs"], key=lambda x: -x["tokens"]):
            bar = "█" * int(r["share"] * 36)
            out.append(f"  {r['tokens']:>6} tok  {r['share'] * 100:>5.1f}%  {bar}")
            out.append(f"          「{r['preview']}」")
        out.append("")

    if result["wasteful"]:
        out.append(f"同义但费 token 的表达（可省约 {result['waste_chars_saved']} 字符"
                   f"≈ {result['waste_tokens_saved']} tokens）：")
        for w in result["wasteful"][:15]:
            out.append(f"  「{w['text']}」→「{w['suggestion']}」"
                       f"（省 {w['chars_saved']} 字符）")
            out.append(f"      {w['reason']}")
        out.append("")
    else:
        out.append("没发现同义但费 token 的表达。")
        out.append("")

    out.append("注：这是估算器，不是精确计数器。"
               "要精确值，请用目标模型的分词器。")
    return "\n".join(out).rstrip()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="tokenlens",
        description="估一段文本会花掉多少 token（仅依赖标准库）",
        epilog=(
            "示例：\n"
            "  python tokenlens.py --file prompt.txt\n"
            "  python tokenlens.py --file prompt.txt --budget 500\n"
            "  python tokenlens.py --file prompt.txt --budget 500 --json\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--file", required=True, help="文本文件")
    ap.add_argument("--budget", type=int, default=0, help="token 预算（可选）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args(argv)

    try:
        with open(args.file, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        print(f"读不了文件：{e}", file=sys.stderr)
        return 2

    if not text.strip():
        print("文件是空的。", file=sys.stderr)
        return 2

    result = weigh(text, args.budget)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(render(result))
    return 1 if result["over_budget"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
