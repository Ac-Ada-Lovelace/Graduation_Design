# 第 4 章接收端压力联调摘要

运行时间：2026-05-11 16:52:46 至 16:53:10（Asia/Shanghai）

## 压力输入参数

- 模拟连接数：80
- 持续时间：20 秒
- 单连接发送间隔：100 ms
- 理论输入速率：约 800 包/秒
- 压力发送端实际发送：15920 包
- 压力发送端连接错误：0

## 接收端落盘统计

- 抽取接收端记录数：15920
- 成功解析记录数：15920
- 接收端成功解析 / 发送端发送：100.00%
- 设备数量：80
- 单设备成功解析记录数范围：199-199
- 状态分布：Success=15920
- 峰值成功解析吞吐：800 包/秒
- 平均成功解析吞吐：758.10 包/秒（按有成功记录的秒统计）

## 生成图表

- `figures/figure-4-receiver-throughput-per-second.png`
- `figures/figure-4-receiver-per-device-success.png`
- `figures/figure-4-receiver-per-device-success-distribution.png`
- `figures/figure-4-receiver-status-distribution.png`
- `figures/figure-4-send-vs-received-success.png`

## 写作边界

本次压力联调用于说明接收端在多连接、高频报文输入下的接收、解析和落盘表现。它不是硬件终端实测，也不评价 NILM 模型识别效果。
