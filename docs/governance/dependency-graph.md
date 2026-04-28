# edu-cloud 模块依赖图

> 自动生成，禁止手写。源：各模块 MODULE.md frontmatter。

```mermaid
flowchart TD
  conduct --> student
  conduct --> school
  grading --> exam
  grading --> scan
  marking --> exam
  marking --> scan
  marking --> grading
  pipeline --> exam
  pipeline --> scan
  pipeline --> grading
  pipeline --> bank
  pipeline --> knowledge
  pipeline --> profile
  pipeline --> student
  pipeline --> adaptive
```
