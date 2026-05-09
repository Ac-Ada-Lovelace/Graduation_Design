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
