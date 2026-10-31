# 恒生电子股吧舆情情感分析与股价关联

抓取东方财富股吧（600570 恒生电子）的帖子，做中文情感分析，并检验**舆情情绪与股价波动之间是否存在可观测的关联**。

## 技术栈

Python、Playwright（浏览器自动化抓取）、jieba 分词、情感词典、scikit-learn、Matplotlib / WordCloud

## 流程

```
main.py                  Playwright 逐页抓取股吧帖子（标题、作者、阅读、评论、时间）→ guba_600570.csv
wordcloud_analysis.py    帖文本分词 + 停用词过滤 → 词云
sentiment_analysis.py    情感打分与分布可视化
stock_trend.py           拉取股价序列，与情绪指标对齐做时序对比
data_overview.py         数据概览与统计
```

四个分析脚本彼此独立、均可单独运行，共享 `guba_600570.csv` 与 `stopwords.txt` 两份输入。

## 情感分析方法

- **词典法**：在通用情感词典基础上补充股吧领域词（如「拉升」「跌停」「割肉」），结合否定词与程度副词做加权；
- **对比实验**：词典法与朴素贝叶斯 / 线性模型在同一批标注样本上对比，用于验证词典在金融口语文本上的可用性；
- **聚合口径**：按天聚合帖子情感均值与情绪方差，与当日涨跌幅、振幅做相关与滞后对比。

## 产出图表

| 文件 | 内容 |
|---|---|
| `Figure1_sentiment_dictionary.png` | 情感词典的得分分布 |
| `Figure2_model_comparison.png` | 不同方法的分类效果对比 |
| `Figure3_sentiment_volatility.png` | 情绪与波动率的对齐关系 |
| `wordcloud.png` | 股吧高频词词云 |
| `stock_price.png` | 同期股价走势 |

## 结论要点

- 股吧情绪与**当日**涨跌高度同向，更像「事后宣泄」而非前瞻信号；对次日收益的预测力很弱；
- 情绪**分歧度（方差）**与波动率的关联，比情绪均值与收益的关联更稳定；
- 词典法在金融口语文本上不如在通用文本上可靠，需领域词补充，这也是后续改用预训练模型的主要动因。

## 运行

```bash
pip install -r requirements.txt
playwright install chromium
python main.py                  # 抓取数据（默认抓 20 页，可改参数）
python sentiment_analysis.py    # 情感打分与分布可视化
python wordcloud_analysis.py    # 生成词云
python stock_trend.py           # 股价与情绪对齐
python data_overview.py         # 数据概览
```

仓库内已附一份抓取结果 `guba_600570.csv`，可直接复现分析部分。

## 说明

仅抓取公开可见的帖子信息用于学术分析，未采集用户隐私字段；脚本默认非无头模式，便于观察页面加载。

## 联系

刘冠湘 · 湖南第一师范学院 · 人工智能专业 · 2027 届 · sxangus@qq.com
