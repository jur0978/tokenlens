# tokenlens

**估一段文本会花掉多少 token。**

`tokenlens` —— 估算文本编码后的 token 数，按段落给出占用并指出可替换的高耗词。

- 零依赖，Python 3.10+ 标准库即可运行
- 单文件，`tokenlens.py` 拷走就能用
- 不联网、不写文件

<!-- ipos:install -->
## 安装

零依赖，Python 3.10+ 即可：

```bash
pip install jur0978-tokenlens
```

装完直接用命令名调用：

```bash
tokenlens --help
```

也可以不用安装，直接把 `tokenlens.py` 拷走用——它只依赖标准库。

## 为什么需要它

计数工具给一个总数；tokenlens 按段归因，并把「换一种说法能省」的高耗表达标出来。

它遵守下面几条自己定的规矩：

1. **标明是估算**。精确计数依赖具体分词器，这里给的是量级估计，这一点必须写在前面，不能让人拿它当精确值。
2. **按段归因**。只给一个总数的话，你不知道该精简哪一段。
3. **指出「同义但费 token」的表达**。这是真正能省下钱的地方。

## 用法

```bash
python tokenlens.py --file prompt.txt
python tokenlens.py --file prompt.txt --budget 500 --json
```

加 `--json` 可以拿到机器可读的结果，便于接到流水线里。

## 已知局限

- token 数按字符与词估算，与具体 tokenizer 有偏差。
- 只报告浪费的短语候选，不自动删改原文。
- 不处理图片、工具调用的隐性开销。

## 跑测试

```bash
python test_tokenlens.py
```

测试用独立的断言与临时数据，不污染工作目录。

## 来源与参考

- Python 标准库文档：<https://docs.python.org/3/>
- GitHub 仓库：<https://github.com/jur0978/tokenlens>

---

## 关于作者

jur0978 做文本的 token 占用估算相关的问题。这个工具先替你回答一个具体问题，再谈别的。

- 个人主页：<https://jur0978.github.io>
- 仓库：<https://github.com/jur0978/tokenlens>

## 许可

MIT，见 [LICENSE](LICENSE)。
