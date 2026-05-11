# NILM 论文引用库 V1

建立日期：2026-05-10

用途：为《面向家庭能耗场景的 NILM 在线监测与推理系统设计与实现》构建可逐步补入正文的候选引用库。本库先解决“引用源是否足够、每篇文献支撑什么论述”的问题，暂不直接决定最终正文编号。正式写入论文时应按正文首次出现顺序重新编号。

## 使用原则

- 优先引用期刊、会议、学位论文、标准和官方文档。
- 网页资料只作为工程背景或系统表达参考，除非最终确实需要，否则不作为核心学术引用。
- 第 1-3 章建议先使用 12-15 篇；全文最终可控制在 20-25 篇。30 篇库用于选择，不代表全部都要进正文。
- 文献序号应在最终稿中按正文首次出现顺序排列，不沿用本库编号。

## 章节覆盖建议

| 章节 | 建议引用来源 | 目的 |
|---|---|---|
| 1.1 研究背景与意义 | R01、R02、R03、R04、R20 | 支撑 NILM 低侵入式、设备级用电分析和工程部署价值 |
| 1.2 国内外研究现状 | R01-R18、R20-R22 | 覆盖起源、传统方法、概率模型、深度学习、数据集、系统部署 |
| 2.1 NILM 技术概述 | R02、R03、R04、R05-R08、R12 | 支撑定义、任务类型、方法分类、评价指标 |
| 2.2 系统关键技术 | R12、R13、R19、R20、R24-R31 | 支撑可复现实验、模型部署、接口服务和数据记录 |
| 3.6 技术经济与可行性分析 | R01、R02、R20、R21、R23 | 支撑低侵入式方案、部署复杂度和系统实现可行性 |

## 强推荐核心引用

| ID | 类型 | 推荐程度 | 引用对象 | 适合放置 |
|---|---|---|---|---|
| R01 | 基础 | 必引 | Hart 1992 NILM 起源 | 1.1、1.2、2.1 |
| R02 | 综述 | 必引 | Zeifman & Roth 2011 综述 | 1.2、2.1 |
| R03 | 综述 | 推荐 | Zoha 等 2012 NILM survey | 1.2、2.1 |
| R09 | 概率模型 | 推荐 | Kolter & Jaakkola 2012 FHMM | 1.2、2.1 |
| R10 | 传统/迁移 | 推荐 | Parson 等 2012 prior models | 1.2 |
| R12 | 数据集 | 推荐 | UK-DALE | 1.2、2.1、7章 |
| R13 | 工具 | 推荐 | NILMTK | 2.1、2.2、7章 |
| R14 | 深度学习 | 推荐 | Neural NILM | 1.2、2.1 |
| R15 | 深度学习 | 推荐 | Seq2Point | 1.2、2.1 |
| R20 | 工程部署 | 必引 | Real-world Deployment | 1.2、2.2、3.6 |
| R21 | 系统论文 | 推荐 | 基于物联网的 NILM 系统设计 | 1.2、3章、4-7章 |
| R22 | 中文算法 | 推荐 | 事件检测与 CNN | 1.2、2.1、5章 |

## 候选引用清单

### A. NILM 基础与综述

| ID | 文献 | 来源/链接 | 支撑点 | 状态 |
|---|---|---|---|---|
| R01 | Hart G W. Nonintrusive appliance load monitoring[J]. Proceedings of the IEEE, 1992, 80(12): 1870-1891. DOI: 10.1109/5.192069. | https://doi.org/10.1109/5.192069 | NILM 起源、单点总负荷推断设备用电思想 | 必引 |
| R02 | Zeifman M, Roth K. Nonintrusive appliance load monitoring: Review and outlook[J]. IEEE Transactions on Consumer Electronics, 2011, 57(1): 76-84. DOI: 10.1109/TCE.2011.5735484. | https://doi.org/10.1109/TCE.2011.5735484 | NILM 方法综述、住宅场景、发展方向 | 必引 |
| R03 | Zoha A, Gluhak A, Imran M A, et al. Non-intrusive load monitoring approaches for disaggregated energy sensing: A survey[J]. Sensors, 2012, 12(12): 16838-16866. DOI: 10.3390/s121216838. | https://www.mdpi.com/1424-8220/12/12/16838 | 负荷特征、分解算法、挑战与未来方向 | 推荐 |
| R04 | Wójcik A, Łukaszewski R, Kowalik R, et al. Nonintrusive appliance load monitoring: An overview, laboratory test results and research directions[J]. Sensors, 2019, 19(16): 3621. DOI: 10.3390/s19163621. | https://www.mdpi.com/1424-8220/19/16/3621 | NILM 概览、实验和研究方向 | 可选 |
| R05 | Liang J, Ng S K K, Kendall G, et al. Load signature study-Part I: Basic concept, structure, and methodology[J]. IEEE Transactions on Power Delivery, 2010, 25(2): 551-560. DOI: 10.1109/TPWRD.2009.2033799. | https://doi.org/10.1109/TPWRD.2009.2033799 | 负荷特征、负荷签名、特征方法 | 推荐 |

### B. 传统方法、事件检测与概率模型

| ID | 文献 | 来源/链接 | 支撑点 | 状态 |
|---|---|---|---|---|
| R06 | Anderson K D, Berges M E, Ocneanu A, et al. Event detection for non intrusive load monitoring[C]//IECON 2012. IEEE, 2012: 3312-3317. DOI: 10.1109/IECON.2012.6389367. | https://doi.org/10.1109/IECON.2012.6389367 | 事件检测、住宅功率数据 | 推荐 |
| R07 | Kolter J Z, Jaakkola T. Approximate inference in additive factorial HMMs with application to energy disaggregation[C]//AISTATS. PMLR, 2012: 1472-1482. | https://proceedings.mlr.press/v22/zico12.html | FHMM、概率模型、能耗分解 | 推荐 |
| R08 | Parson O, Ghosh S, Weal M, et al. Non-intrusive load monitoring using prior models of general appliance types[C]//AAAI. 2012: 356-362. DOI: 10.1609/AAAI.V26I1.8162. | https://dblp.org/rec/conf/aaai/ParsonGWR12 | 设备先验模型、泛化与低标注需求 | 推荐 |
| R09 | Kolter J Z, Johnson M J. REDD: A public data set for energy disaggregation research[C]//Workshop on Data Mining Applications in Sustainability, 2011. | https://www.cs.cmu.edu/~zkolter/pubs/kolter-kddsust11.pdf | REDD 数据集、能耗分解评估 | 推荐 |

### C. 数据集、评价与工具

| ID | 文献 | 来源/链接 | 支撑点 | 状态 |
|---|---|---|---|---|
| R10 | Kelly J, Knottenbelt W. The UK-DALE dataset, domestic appliance-level electricity demand and whole-house demand from five UK homes[J]. Scientific Data, 2015, 2: 150007. DOI: 10.1038/sdata.2015.7. | https://www.nature.com/articles/sdata20157 | UK-DALE 数据集、总表和设备级真值 | 推荐 |
| R11 | Makonin S, Popowich F, Bartram L, et al. AMPds: A public dataset for load disaggregation and eco-feedback research[C]//IEEE EPEC, 2013. DOI: 10.1109/EPEC.2013.6802949. | https://doi.org/10.1109/EPEC.2013.6802949 | AMPds 数据集、负荷分解与反馈研究 | 可选 |
| R12 | Batra N, Kelly J, Parson O, et al. NILMTK: An open source toolkit for non-intrusive load monitoring[C]//ACM e-Energy. 2014: 265-276. DOI: 10.1145/2602044.2602051. | https://doi.org/10.1145/2602044.2602051 | 可复现实验、数据集解析、评价指标 | 推荐 |
| R13 | Pereira L, Nunes N. A dataset for non-intrusive load monitoring: Design and implementation[J]. Energies, 2020, 13(20): 5371. DOI: 10.3390/en13205371. | https://www.mdpi.com/1996-1073/13/20/5371 | NILM 数据集设计、数据采集与标注 | 可选 |
| R14 | Pereira L, Nunes N. A critical review of state-of-the-art non-intrusive load monitoring datasets[J]. Electric Power Systems Research, 2021, 192: 106921. DOI: 10.1016/j.epsr.2020.106921. | https://doi.org/10.1016/j.epsr.2020.106921 | 数据集综述、评估难点 | 可选 |

### D. 深度学习 NILM

| ID | 文献 | 来源/链接 | 支撑点 | 状态 |
|---|---|---|---|---|
| R15 | Kelly J, Knottenbelt W. Neural NILM: Deep neural networks applied to energy disaggregation[C]//BuildSys. 2015. | https://arxiv.org/abs/1507.06594 | LSTM、去噪自编码器、神经网络 NILM | 推荐 |
| R16 | Zhang C, Zhong M, Wang Z, et al. Sequence-to-point learning with neural networks for non-intrusive load monitoring[C]//AAAI. 2018: 2604-2611. DOI: 10.1609/aaai.v32i1.11873. | https://doi.org/10.1609/aaai.v32i1.11873 | Seq2Point、滑动窗口、CNN NILM | 推荐 |
| R17 | Bonfigli R, Felicetti A, Principi E, et al. Denoising autoencoders for non-intrusive load monitoring: Improvements and comparative evaluation[J]. Energy and Buildings, 2018, 158: 1461-1474. DOI: 10.1016/j.enbuild.2017.11.054. | https://doi.org/10.1016/j.enbuild.2017.11.054 | 去噪自编码器、深度学习对比 | 可选 |
| R18 | Kaselimi M, Voulodimos A, Protopapadakis E, et al. EnerGAN: A generative adversarial network for energy disaggregation[C]//ICASSP. 2020. | https://sigport.org/documents/energan-generative-adversarial-network-energy-disaggregation | GAN 能耗分解、深度模型扩展 | 可选 |
| R19 | Massidda L, Marrocu M. Non-intrusive load monitoring using deep neural networks: A review[EB/OL]. arXiv:2306.05017, 2023. | https://arxiv.org/abs/2306.05017 | 深度学习 NILM 综述 | 可选 |

### E. 工程部署与系统实现

| ID | 文献 | 来源/链接 | 支撑点 | 状态 |
|---|---|---|---|---|
| R20 | Xue J, Zhang Y, Wang X, et al. Towards real-world deployment of NILM systems: Challenges and practices[EB/OL]. arXiv:2409.14821, 2024. | https://arxiv.org/abs/2409.14821 | 真实部署、工程落地、评估与运行挑战 | 必引 |
| R21 | 何勇, 王晓丽, 肖海飞, 等. 基于物联网的非侵入式用电器在线监测系统设计与实现[J]. 智能计算机与应用, 2021, 11(12): 158-165. | 本地：`papers/iot_nilm_online_monitoring_system_design_2021.pdf` | 系统型 NILM 论文结构、采集、软件系统、测试 | 推荐 |
| R22 | 凌家源, 彭勇刚. 基于事件检测与 CNN 模型的非侵入式负荷识别方法及实现[J]. 电工电能新技术, 2021, 40(3): 46-54. DOI: 10.12067/ATEEE2010034. | https://ateee.iee.ac.cn/CN/10.12067/ATEEE2010034 | 事件检测、CNN、实验评价 | 推荐 |
| R23 | 基于云平台的非侵入式负荷监测与识别系统[EB/OL]. | https://www.chinaaet.com/article/3000090589 | 云平台 + 监测识别系统的工程表达 | 仅作背景 |

### F. 模型部署、接口服务与数据记录

| ID | 文献 | 来源/链接 | 支撑点 | 状态 |
|---|---|---|---|---|
| R24 | ONNX. Open Neural Network Exchange[EB/OL]. | https://onnx.ai/ | 模型互操作标准、模型包设计背景 | 视实现使用 |
| R25 | ONNX Runtime. ONNX Runtime documentation[EB/OL]. | https://onnxruntime.ai/docs | 模型推理运行时、服务化部署 | 视实现使用 |
| R26 | FastAPI. FastAPI documentation[EB/OL]. | https://fastapi.tiangolo.com/ | Python HTTP API 服务框架 | 视实现使用 |
| R27 | JSON Lines. JSON Lines text file format[EB/OL]. | https://jsonlines.org/ | JSONL 留痕、逐行结构化记录 | 视实现使用 |
| R28 | Fielding R T. Architectural styles and the design of network-based software architectures[D]. University of California, Irvine, 2000. | https://www.ics.uci.edu/~fielding/pubs/dissertation/top.htm | REST 架构思想、接口设计背景 | 可选 |
| R29 | OpenAPI Initiative. OpenAPI Specification v3.2.0[EB/OL]. 2025. | https://spec.openapis.org/oas/latest.html | API 描述、接口文档规范 | 可选 |
| R30 | Fielding R, Nottingham M, Reschke J. HTTP Semantics: RFC 9110[S/OL]. IETF, 2022. | https://www.rfc-editor.org/rfc/rfc9110 | HTTP 方法、状态语义、接口协议 | 可选 |
| R31 | Eddy W. Transmission Control Protocol (TCP): RFC 9293[S/OL]. IETF, 2022. | https://www.rfc-editor.org/rfc/rfc9293 | TCP 传输协议、采集链路通信依据 | 视实现使用 |

## 初步插入方案

### 第 1 章

- 1.1 中“非侵入式负荷监测提供低侵入技术思路”后可引 R01、R02。
- 1.1 中“系统不仅需要模型本身，还需要采集、推理、展示和测试链路”后可引 R20。
- 1.2 第一段 Hart 和早期人工特征方法可引 R01、R05。
- 1.2 第二段传统机器学习、概率模型和深度学习方法可引 R07、R08、R15、R16。
- 1.2 第三段公开数据集和工程化部署可引 R10、R12、R20、R21。

### 第 2 章

- 2.1 定义和任务描述可引 R02、R03、R04。
- 2.1 方法分类可引 R05-R08、R15-R17。
- 2.1 指标和可复现实验可引 R12。
- 2.2 TCP 采集链路可引 R31，模型包、推理服务、在线回放可引 R20、R24-R27。

### 第 3 章

- 3.2 系统总体架构可引 R20、R21、R23。
- 3.5 模型包契约和接口设计可引 R24-R30。
- 3.6 技术经济与可行性分析可引 R01、R02、R20、R21。

## 暂缓引用

- 网页类资料 R23、R26-R30 不建议在第 1 章研究现状中使用。
- ONNX/ONNX Runtime/FastAPI/JSON Lines 只有在最终实现确实采用时再进入正式参考文献表。
- R18、R19 可作为扩展材料，若篇幅有限可不进入最终稿。
