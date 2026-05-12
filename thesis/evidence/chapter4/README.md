# 第 4 章证据目录

本目录存放第 4 章“数据采集与预处理模块设计实现”的证据材料。

## 正文优先使用

- `receiver-stress-20260511-165152/`：接收端压力联调证据，是第 4 章正文的主要运行证据。
  - `receiver_stress_summary.md`：压力联调摘要。
  - `receiver_stress_records.jsonl`：从接收端 JSONL 中抽取的本次压力联调记录。
  - `stress_sender.py`：压力发送脚本。
  - `stress_sender.stdout.log`：压力发送端日志。
  - `figures/figure-4-receiver-throughput-per-second.png`：接收端每秒成功解析吞吐图。
  - `figures/figure-4-send-vs-received-success.png`：发送量与接收端成功解析量对比图。
  - `figures/figure-4-receiver-per-device-success-distribution.png`：单设备成功解析数量分布图。

## 补充证据

- `run-20260511-163157/`：常规 20 设备模拟终端联调证据。
  - `run_summary.md`：常规联调摘要。
  - `run_records.jsonl`：本次常规联调抽取记录。
  - `simulator.stdout.log`：模拟终端日志。
  - `figures/figure-4-1-data-collection-flow.png`：数据采集与预处理流程图。
  - `figures/figure-4-4-packet-layout.png`：44 字节报文结构示意图。
- `measurement_samples.jsonl`：从 Stage-01 历史运行产物中精选的 4 条 JSONL 记录，保留为早期样例。

## 仍缺材料

- 采集后台 GUI 总览页截图。
- 设备详情页或协议包详情页截图。
