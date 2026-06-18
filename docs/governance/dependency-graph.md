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
  exam_import --> exam
  exam_import --> grading
  exam_import --> pipeline
  exam_import --> profile
  exam_import --> scan
  exam_import --> student
  grading --> card
  grading --> exam
  grading --> scan
  homework --> exam
  homework --> scan
  homework --> bank
  knowledge --> exam
  knowledge --> knowledge_tree
  knowledge_tree --> adaptive
  marking --> exam
  marking --> scan
  marking --> grading
  pipeline --> exam
  pipeline --> grading
  pipeline --> knowledge
  pipeline --> knowledge_tree
  pipeline --> profile
  pipeline --> scan
  pipeline --> student
  portal --> calendar
  portal --> homework
  profile --> knowledge_tree
  scan --> exam
  scan --> card
  scan --> student
```
