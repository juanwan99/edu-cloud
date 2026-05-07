# edu-cloud 模块依赖图

> 自动生成，禁止手写。源：各模块 MODULE.md frontmatter。

```mermaid
flowchart TD
  adaptive --> knowledge_tree
  analytics --> exam
  analytics --> scan
  analytics --> grading
  analytics --> student
  analytics --> knowledge
  analytics --> knowledge_tree
  analytics --> profile
  analytics --> studio
  bank --> exam
  bank --> student
  calendar --> school
  card --> exam
  conduct --> student
  conduct --> school
  exam --> grading
  exam --> pipeline
  grading --> exam
  grading --> scan
  homework --> exam
  homework --> scan
  homework --> bank
  knowledge --> knowledge_tree
  knowledge_tree --> knowledge
  knowledge_tree --> exam
  knowledge_tree --> adaptive
  marking --> exam
  marking --> scan
  marking --> grading
  menu --> school
  pipeline --> exam
  pipeline --> scan
  pipeline --> grading
  pipeline --> bank
  pipeline --> knowledge
  pipeline --> profile
  pipeline --> student
  pipeline --> adaptive
  profile --> student
  profile --> knowledge_tree
  profile --> analytics
  scan --> exam
  scan --> card
  studio --> school
```
