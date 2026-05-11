# 论文参考资料归档索引

归档日期：2026-05-08

本目录用于保存论文大纲调研阶段参考过的公开资料。PDF 文件用于后续阅读、引用和章节结构参考；HTML 文件用于保留网页快照，避免链接变化后找不到原始信息。

## 系统设计与 NILM 相关论文

1. 基于物联网的非侵入式用电器在线监测系统设计与实现
   - 本地文件：`papers/iot_nilm_online_monitoring_system_design_2021.pdf`
   - 来源 URL：https://cs.hit.edu.cn/_upload/article/files/f0/55/3f606a284f35a237ca314648a64d/7edc5cca-de5d-4a3b-a991-2f6c00c1bdb8.pdf
   - 用途：参考系统型 NILM 论文的章节安排。该文包含系统总体设计、硬件采集、识别算法、软件系统、测试分析等结构。

2. Towards Real-world Deployment of NILM Systems
   - 本地文件：`papers/towards_real_world_deployment_of_nilm_systems_2024_arxiv.pdf`
   - 摘要页快照：`webpages/towards_real_world_deployment_of_nilm_systems_2024_arxiv_abs.html`
   - 来源 URL：https://arxiv.org/abs/2409.14821
   - PDF URL：https://arxiv.org/pdf/2409.14821
   - 用途：参考 NILM 从算法到真实部署时需要关注的问题，包括部署链路、数据集、评估方式和工程落地挑战。

3. 基于事件检测与 CNN 模型的非侵入式负荷识别方法及实现
   - 本地文件：`papers/event_detection_cnn_nilm_method_2021_ateee.pdf`
   - 网页快照：`webpages/event_detection_cnn_nilm_method_ateee.html`
   - 来源 URL：https://ateee.iee.ac.cn/CN/10.12067/ATEEE2010034
   - PDF URL：https://ateee.iee.ac.cn/CN/PDF/10.12067/ATEEE2010034
   - 用途：参考 NILM 算法、事件检测、嵌入式实现和实验评价写法。

## 网页资料

4. 基于云平台的非侵入式负荷监测与识别系统
   - 本地文件：`webpages/cloud_based_nilm_monitoring_recognition_system_chinaaet.html`
   - 来源 URL：https://www.chinaaet.com/article/3000090589
   - 用途：参考“云平台 + NILM + 监测识别系统”的系统组成和工程表达方式。

5. 基于软件的毕业设计论文的书写
   - 本地文件：`webpages/software_graduation_design_thesis_writing_cnblogs.html`
   - 来源 URL：https://www.cnblogs.com/c-programing-language/p/6878838.html
   - 用途：参考软件系统类毕业论文常见章节，包括绪论、需求分析、概要设计、详细设计、系统测试等。

## 使用建议

- 写第 1 章“研究现状”时，优先阅读资料 1、2、3。
- 写第 3 章“系统总体设计”时，优先参考资料 1、4 的系统结构表达。
- 写第 4-5 章“采集与推理模块实现”时，结合资料 1、3 与本仓库 `stages/` 下代码和文档。
- 写第 7 章“系统测试与结果分析”时，参考资料 1、2、3 的实验指标与测试组织方式。
- 网页资料不一定适合作为正式参考文献，正式论文参考文献应优先使用期刊、会议、学位论文、标准、官方文档等稳定来源。

## 扩充引用库

- `reference_library_v1.md`
  - 建立日期：2026-05-10
  - 内容：围绕 NILM 起源、综述、传统方法、数据集、深度学习、真实部署、系统实现和接口技术整理 31 篇左右候选引用源，并给出适合插入的章节位置。
  - 用途：作为后续将 V2.1 正文改为“引用版”的人工工作底稿。

- `references_seed_v1.bib`
  - 建立日期：2026-05-10
  - 内容：与 `reference_library_v1.md` 对应的 BibTeX 种子库，共 31 条。
  - 用途：后续可转换为 GB/T 7714 参考文献表，或作为 Zotero/JabRef 等工具导入材料。

- `引用格式审查与补入方案_V1.md`
  - 建立日期：2026-05-10
  - 内容：按附件四 `9 毕业设计（论文）的撰写规范及要求.doc` 汇总正文引用、参考文献表和顺序编码制要求。
  - 用途：作为前三章补入正文引用和生成参考文献表前的格式执行底稿。

- `第1章引用准备表_V1.md`
  - 建立日期：2026-05-10
  - 内容：基于前三章正文稿 V2.1 和引用库，整理第 1 章拟使用文献、暂定编号和逐段放置建议。
  - 用途：作为第 1 章正式插入正文引用前的确认表。

## 正文引用版稿件

- `../前三章_正文草稿_V2_4.md`
  - 建立日期：2026-05-10
  - 内容：在 V2.3 基础上继续补入第 2 章细粒度正文引用，正文引用采用单点编号，不使用区间或合并编号。
  - 用途：作为后续第 3 章继续补引用、同步 DOCX 的 Markdown 源稿。

- `../华北电力大学本科毕业设计论文_前三章正文稿V2_4.docx`
  - 建立日期：2026-05-10
  - 内容：与 V2.4 Markdown 对应的 DOCX 稿件，正文引用已设为上标，参考文献表扩展到 19 条。
  - 用途：作为 V2.5 之前的前三章 DOCX 引用版。

- `../前三章_正文草稿_V2_5.md`
  - 建立日期：2026-05-10
  - 内容：在 V2.4 基础上继续补入第 3 章细粒度正文引用，重点覆盖总体架构、数据流、模型包契约、HTTP/API 接口和技术经济可行性分析。
  - 用途：作为第 1-3 章均已补入正文引用后的 Markdown 源稿。

- `../华北电力大学本科毕业设计论文_前三章正文稿V2_5.docx`
  - 建立日期：2026-05-10
  - 内容：与 V2.5 Markdown 对应的 DOCX 稿件，正文引用已设为上标，参考文献表扩展到 20 条。
  - 用途：作为当前可审阅的前三章 DOCX 引用版。

- `../前三章_正文草稿_V2_6.md`
  - 建立日期：2026-05-10
  - 内容：按 V2.5 审阅报告进行小修订，收敛完成式表述，补全电子文献 URL 和访问日期，并给模型包契约加入设计约定边界。
  - 用途：作为继续进入第 4 章前的前三章 Markdown 修订稿。

- `../华北电力大学本科毕业设计论文_前三章正文稿V2_6.docx`
  - 建立日期：2026-05-10
  - 内容：与 V2.6 Markdown 对应的 DOCX 稿件，封面版本更新为 V2.6，正文引用保持上标。
  - 用途：作为当前可审阅的前三章 DOCX 修订版。
