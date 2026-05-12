# 第 4 章采集联调运行摘要

运行时间：2026-05-11 16:32:39 至 16:32:56（Asia/Shanghai）

## 数据来源

- 原始文件：`stages\stage-01-data-collection\src\GraduationDesign.App\bin\Debug\net8.0-windows\data\measurements-20260511.jsonl`
- 本次抽取：`thesis\evidence\chapter4\run-20260511-163157\run_records.jsonl`
- 模拟终端日志：`simulator.stdout.log`
- 运行元数据：`run-metadata.txt`

## 统计结果

- 抽取报文数：320
- 成功解析报文数：300
- 设备数量：20
- 设备 ID 范围：1-20
- 解析状态：Success=300, TransportError=20
- 起始接收时间 UTC：2026-05-11T08:32:39.584790+00:00
- 结束接收时间 UTC：2026-05-11T08:32:54.453586+00:00
- 平均功率最高设备：20（7650.89 W）

## 生成图表

- `figures/figure-4-1-data-collection-flow.png`
- `figures/figure-4-record-count-by-device.png`
- `figures/figure-4-total-power-timeseries.png`
- `figures/figure-4-device1-phase-power.png`
- `figures/figure-4-average-power-by-device.png`
- `figures/figure-4-4-packet-layout.png`

## JSONL 样例

```json
{"receivedAt":"2026-05-11T08:32:39.5847902Z","remoteEndPoint":"127.0.0.1:52412","deviceId":3,"deviceName":"厨房回路","reportTimeUtc":"2026-05-11T08:32:39Z","currentA":6.7127743,"currentB":3.9878902,"currentC":2.7351851,"voltageA":219.93794,"voltageB":218.60477,"voltageC":220.80348,"powerA":1343.5183,"powerB":767.1592,"powerC":513.34766,"parseStatus":"Success","errorMessage":"","rawHex":"03 00 00 00 27 94 01 6A 0C CF D6 40 98 39 7F 40 46 0D 2F 40 1D F0 5B 43 D2 9A 5A 43 B1 CD 5C 43 96 F0 A7 44 30 CA 3F 44 40 56 00 44"}
{"receivedAt":"2026-05-11T08:32:39.6052704Z","remoteEndPoint":"127.0.0.1:52421","deviceId":12,"deviceName":"插座回路B","reportTimeUtc":"2026-05-11T08:32:39Z","currentA":13.4779,"currentB":8.129274,"currentC":5.951084,"voltageA":220.03683,"voltageB":223.22296,"voltageC":218.52513,"powerA":2698.7273,"powerB":1596.8839,"powerC":1105.3922,"parseStatus":"Success","errorMessage":"","rawHex":"0C 00 00 00 27 94 01 6A 7A A5 57 41 82 11 02 41 48 6F BE 40 6E 09 5C 43 14 39 5F 43 6F 86 5A 43 A3 AB 28 45 49 9C C7 44 8D 2C 8A 44"}
{"receivedAt":"2026-05-11T08:32:39.6054664Z","remoteEndPoint":"127.0.0.1:52422","deviceId":13,"deviceName":"玄关回路","reportTimeUtc":"2026-05-11T08:32:39Z","currentA":14.812717,"currentB":8.648549,"currentC":6.041605,"voltageA":219.00598,"voltageB":222.72049,"voltageC":219.4854,"powerA":2952.1072,"powerB":1695.064,"powerC":1127.1375,"parseStatus":"Success","errorMessage":"","rawHex":"0D 00 00 00 27 94 01 6A E4 00 6D 41 75 60 0A 41 D4 54 C1 40 88 01 5B 43 72 B8 5E 43 43 7C 5B 43 B7 81 38 45 0C E2 D3 44 66 E4 8C 44"}
```

## 写作边界

本次数据来自模拟终端联调，可用于说明采集链路、协议解析和数据留痕机制，但不应表述为真实家庭场景采集结果，也不用于评价 NILM 模型识别精度。
