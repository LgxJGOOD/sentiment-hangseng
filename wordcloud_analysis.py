import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

# =========================
# 解决中文乱码问题
# =========================
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

# =========================
# 模拟ADF检验结果数据
# =========================
adf_result = pd.DataFrame({
    '变量': ['投资者情绪指数', '股价波动率', '信息不对称程度'],
    'ADF统计量': [-4.82, -3.96, -5.21],
    'P值': [0.001, 0.013, 0.000],
    '检验结果': ['平稳', '平稳', '平稳']
})

# =========================
# 模拟基准回归结果数据
# =========================
regression_result = pd.DataFrame({
    '变量': ['投资者情绪指数', '成交量', '换手率', '大盘收益率', '个股收益率'],
    '回归系数': [0.582, 0.214, 0.176, -0.135, 0.428],
    'T值': [5.82, 3.14, 2.76, -2.11, 4.67],
    'P值': [0.000, 0.002, 0.006, 0.035, 0.000]
})

# ==================================================
# 图1：ADF单位根检验
# ==================================================
fig1 = plt.figure(figsize=(10, 6))
ax1 = fig1.add_subplot(111)

ax1.axis('off')
ax1.set_title('平稳性检验：ADF单位根检验', fontsize=15)

table1 = ax1.table(
    cellText=adf_result.values,
    colLabels=adf_result.columns,
    cellLoc='center',
    loc='center'
)

table1.auto_set_font_size(False)
table1.set_fontsize(11)
table1.scale(1.2, 2)

# 表头样式
for (row, col), cell in table1.get_celld().items():
    if row == 0:
        cell.set_facecolor('#4F81BD')
        cell.set_text_props(color='white', weight='bold')
    else:
        cell.set_facecolor('#F2F2F2')

ax1.text(
    0.5, -0.25,
    "所有变量ADF检验p值均小于0.05，说明序列平稳，可直接进行回归分析。",
    transform=ax1.transAxes,
    ha='center',
    fontsize=10
)

plt.tight_layout()
plt.show()


# ==================================================
# 图2：基准回归分析
# ==================================================
fig2 = plt.figure(figsize=(10, 6))
ax2 = fig2.add_subplot(111)

ax2.axis('off')
ax2.set_title('基准回归分析：投资者情绪对股价波动的影响', fontsize=15)

table2 = ax2.table(
    cellText=regression_result.values,
    colLabels=regression_result.columns,
    cellLoc='center',
    loc='center'
)

table2.auto_set_font_size(False)
table2.set_fontsize(11)
table2.scale(1.2, 2)

# 表头样式
for (row, col), cell in table2.get_celld().items():
    if row == 0:
        cell.set_facecolor('#C0504D')
        cell.set_text_props(color='white', weight='bold')
    else:
        cell.set_facecolor('#F9F9F9')

ax2.text(
    0.5, -0.30,
    "回归结果显示：投资者情绪显著正向影响股价波动，且在1%水平显著。",
    transform=ax2.transAxes,
    ha='center',
    fontsize=10
)

plt.tight_layout()
plt.show()