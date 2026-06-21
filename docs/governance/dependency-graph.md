# edu-cloud 模块依赖图

> 自动生成，禁止手写。源：各模块 MODULE.md frontmatter。

```mermaid
flowchart TD
  academic --> calendar
  academic --> student
  analytics --> exam
  analytics --> scan
  analytics --> grading
  analytics --> student
  analytics --> knowledge
  analytics --> knowledge_tree
  analytics --> profile
  bank --> exam
  bank --> student
  card --> exam
  conduct --> academic
  conduct --> bank
  conduct --> exam
  conduct --> profile
  conduct --> student
  grading --> card
  grading --> exam
  grading --> scan
  homework --> exam
  homework --> scan
  homework --> bank
  knowledge --> exam
  knowledge --> knowledge_tree
  knowledge_tree --> adaptive
  portal --> calendar
  portal --> homework
  profile --> knowledge_tree
  scan --> exam
  scan --> card
  scan --> student
```
