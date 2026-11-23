# 合成材料：LaTeX 工程与模板约束

## 工程结构
主文件 main.tex 使用 \documentclass[twocolumn]{article}，子文件为 sections/intro.tex 与 sections/method.tex。导言区依次加载 amsmath、booktabs、graphicx 与 hyperref。

## 公式与编号
式 (3) 使用 \begin{align} 环境，含三个对齐点，并以 \label{eq:loss} 标记；正文以 \eqref{eq:loss} 引用。式 (4) 的变量 η 与 σ 使用正体。

## 表格
表 2 为三线表，列格式为 lcc，包含 6 个数据行；最宽单元格为 “Post-treatment recovery rate (%)”。

## 交叉引用与文献
正文含 \ref{fig:framework}、\ref{tab:params} 与 \cite{zhang2023,li2024}；bibliography.bib 中仅有 zhang2023 一条。

## 模板必填项与编译轮次
模板要求 title、author、abstract 与 keywords 四项齐全。构建命令为 pdflatex → bibtex → pdflatex → pdflatex，TeX 发行版为 TeX Live 2023。

## 已报告的问题
编译日志显示第 42 行 “Undefined control sequence \epsilon”，第 57 行 “Reference `fig:framework' on page 3 undefined”。

本材料为合成示例，仅用于离线演练本 Skill。
