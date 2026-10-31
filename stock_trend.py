import json
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
import matplotlib

# 设置中文字体
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS', 'sans-serif']
matplotlib.rcParams['axes.unicode_minus'] = False

with open('data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

hq = data['hq']
dates = [datetime.strptime(row[0], '%Y-%m-%d') for row in hq]
close_prices = [float(row[2]) for row in hq]

dates.reverse()
close_prices.reverse()

fig, ax = plt.subplots(figsize=(14, 6))
ax.plot(dates, close_prices, linewidth=1.5, color='#d62728')
ax.fill_between(dates, close_prices, alpha=0.15, color='#d62728')

ax.set_title(f"{data['code']} 股价走势", fontsize=14, fontweight='bold')
ax.set_xlabel('日期', fontsize=11)
ax.set_ylabel('收盘价', fontsize=11)
ax.grid(True, alpha=0.3, linestyle='--')

# 根据数据范围自动计算间隔，显示部分月份标签
num_dates = len(dates)
if num_dates > 60:
    interval = 3  # 每3个月显示一次
elif num_dates > 30:
    interval = 2
else:
    interval = 1
ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
ax.xaxis.set_major_locator(mdates.MonthLocator(interval=interval))
plt.xticks(rotation=45)
plt.tight_layout()

plt.savefig('stock_price.png', dpi=150, bbox_inches='tight')
plt.show()